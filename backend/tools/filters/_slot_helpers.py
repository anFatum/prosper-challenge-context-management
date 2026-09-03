"""
Shared Redis slot-store logic for Phase 4 filter tools.

Key schema (all keys expire at SESSION_TTL):
  session:{id}:slots          ZSET  composite score → slot_id   (full set)
  session:{id}:slot_data      HASH  slot_id → JSON metadata
  session:{id}:loc:{loc_id}   ZSET  0 → slot_id   (membership)
  session:{id}:prov:{prov_id} ZSET  0 → slot_id
  session:{id}:time:{bucket}  ZSET  0 → slot_id   (morning/afternoon/evening)
  session:{id}:current        ZSET  intersected view of active filters
"""

import json
from datetime import date, time

import redis.asyncio as aioredis

SESSION_TTL = 900  # 15 minutes


# ── Score helpers ─────────────────────────────────────────────────────────────

def _time_bucket(t: time) -> int:
    if t.hour < 12:
        return 0  # morning
    elif t.hour < 17:
        return 1  # afternoon
    return 2  # evening


def _composite_score(slot_date: date, start: time, provider_rank: int) -> float:
    days = max(0, (slot_date - date.today()).days)
    return days * 1000 + _time_bucket(start) * 100 + provider_rank


# ── Build slot store ──────────────────────────────────────────────────────────

async def build_slot_store(
    session_id: str,
    appt_type_id: str,
    pool,           # asyncpg.Pool
    redis: aioredis.Redis,
) -> int:
    """Populate all session Redis keys from DB. Returns total slot count."""
    rows = await pool.fetch(
        """
        SELECT
            cs.id::text,
            cs.provider_id,
            cs.location_id,
            cs.date,
            cs.start_time,
            cs.end_time,
            p.name         AS provider_name,
            p.title        AS provider_title,
            p.accepting_new AS accepting_new,
            l.name         AS location_name
        FROM calendar_slots cs
        JOIN eligible_pairs ep
            ON  ep.provider_id  = cs.provider_id
            AND ep.location_id  = cs.location_id
            AND ep.appt_type_id = $1
        JOIN providers p ON p.id = cs.provider_id
        JOIN locations  l ON l.id = cs.location_id
        WHERE cs.available = TRUE
          AND cs.date >= $2
        ORDER BY cs.date, cs.start_time
        """,
        appt_type_id,
        date.today(),
    )

    if not rows:
        return 0

    base_key = f"session:{session_id}:slots"
    data_key = f"session:{session_id}:slot_data"

    # Providers who accept new patients rank lower (shown first); non-accepting rank higher.
    # Within each group, sort alphabetically for stability.
    accepting     = sorted({r["provider_id"] for r in rows if r["accepting_new"]})
    not_accepting = sorted({r["provider_id"] for r in rows if not r["accepting_new"]})
    prov_rank = {pid: i for i, pid in enumerate(accepting + not_accepting)}

    BUCKETS = ["morning", "afternoon", "evening"]

    async with redis.pipeline(transaction=False) as pipe:
        for r in rows:
            slot_id = r["id"]
            score = _composite_score(r["date"], r["start_time"], prov_rank[r["provider_id"]])
            bucket = BUCKETS[_time_bucket(r["start_time"])]

            pipe.zadd(base_key, {slot_id: score})
            pipe.zadd(f"session:{session_id}:loc:{r['location_id']}", {slot_id: 0})
            pipe.zadd(f"session:{session_id}:prov:{r['provider_id']}", {slot_id: 0})
            pipe.zadd(f"session:{session_id}:time:{bucket}", {slot_id: 0})
            pipe.hset(data_key, slot_id, json.dumps({
                "provider_id":    r["provider_id"],
                "location_id":    r["location_id"],
                "provider_name":  r["provider_name"],
                "provider_title": r["provider_title"] or "",
                "location_name":  r["location_name"],
                "date":           r["date"].isoformat(),
                "start_time":     r["start_time"].strftime("%H:%M"),
                "end_time":       r["end_time"].strftime("%H:%M"),
            }))

        await pipe.execute()

    # Set TTL on every key we just wrote
    all_keys = await redis.keys(f"session:{session_id}:*")
    if all_keys:
        async with redis.pipeline(transaction=False) as pipe:
            for k in all_keys:
                pipe.expire(k, SESSION_TTL)
            await pipe.execute()

    return await redis.zcard(base_key)


# ── Filter computation ────────────────────────────────────────────────────────

async def recompute_current(
    session_id: str,
    active_filters: list[dict],
    redis: aioredis.Redis,
) -> tuple[str, int]:
    """Intersect the base slot set with all active filters.
    Returns (active_key, slot_count).
    """
    base_key = f"session:{session_id}:slots"

    if not active_filters:
        return base_key, await redis.zcard(base_key)

    current_key = f"session:{session_id}:current"
    # Weight base=1 (preserves score), each filter=0 (membership-only).
    # aggregate=max → result score = max(composite_score, 0) = composite_score.
    weights = {base_key: 1}
    for f in active_filters:
        weights[f["key"]] = 0

    await redis.zinterstore(current_key, weights, aggregate="max")

    # Carry forward the base TTL
    ttl = await redis.ttl(base_key)
    if ttl > 0:
        await redis.expire(current_key, ttl)

    return current_key, await redis.zcard(current_key)


# ── Option fetching ───────────────────────────────────────────────────────────

def _fmt_time(t: str) -> str:
    """'09:30' → '9:30 AM'"""
    h, m = map(int, t.split(":"))
    suffix = "AM" if h < 12 else "PM"
    return f"{h % 12 or 12}:{m:02d} {suffix}"


async def get_options(
    session_id: str,
    active_key: str,
    cursor: int,
    redis: aioredis.Redis,
    n: int = 3,
) -> list[dict]:
    """Fetch n slot summaries starting at cursor rank in the active key."""
    slot_ids = await redis.zrange(active_key, cursor, cursor + n - 1)
    if not slot_ids:
        return []

    data_key = f"session:{session_id}:slot_data"
    raw = await redis.hmget(data_key, *slot_ids)

    options = []
    for slot_id, r in zip(slot_ids, raw):
        if r is None:
            continue
        d = json.loads(r)
        title = f" ({d['provider_title']})" if d["provider_title"] else ""
        options.append({
            "slot_id":  slot_id,
            "provider": f"{d['provider_name']}{title}",
            "location": d["location_name"],
            "date":     d["date"],
            "time":     f"{_fmt_time(d['start_time'])} – {_fmt_time(d['end_time'])}",
        })
    return options


# ── Filter application helper (used by filter_by_* tools) ────────────────────

async def apply_filter(
    flow_manager,
    filter_entry: dict,
) -> dict:
    """Add filter_entry to active_filters, recompute, update cursor, return result."""
    from db.redis import get_redis

    session_id = flow_manager.state["session_id"]
    redis = get_redis()

    # Verify the filter key has members (e.g. the location actually has slots)
    if not await redis.zcard(filter_entry["key"]):
        # State is unchanged — previous options are still valid.
        _, still_available = await recompute_current(
            session_id, flow_manager.state.get("active_filters", []), redis
        )
        return {
            "status": "no_slots",
            "message": f"No available slots match that {filter_entry['type']}.",
            "previous_options_still_available": True,
            "still_available_total": still_available,
        }

    active_filters: list[dict] = list(flow_manager.state.get("active_filters", []))
    # Replace existing filter of same type rather than stacking duplicates
    active_filters = [f for f in active_filters if f["type"] != filter_entry["type"]]
    active_filters.append(filter_entry)

    active_key, count = await recompute_current(session_id, active_filters, redis)

    if count == 0:
        # State is unchanged — roll back and report what's still available.
        _, still_available = await recompute_current(
            session_id, flow_manager.state.get("active_filters", []), redis
        )
        return {
            "status": "no_slots",
            "message": "No slots match the combined filters. Try clearing one.",
            "previous_options_still_available": True,
            "still_available_total": still_available,
        }

    options = await get_options(session_id, active_key, 0, redis)
    flow_manager.state["active_filters"] = active_filters
    flow_manager.state["slot_cursor"] = len(options)

    return {"status": "ok", "total": count, "options": options}