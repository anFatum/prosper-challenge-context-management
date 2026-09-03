from datetime import date

from pipecat_flows import FlowManager, FlowsFunctionSchema

from db.redis import get_redis
from tools.filters._slot_helpers import SESSION_TTL, apply_filter, parse_date


async def _handler(args: dict, flow_manager: FlowManager) -> dict:
    raw = args.get("date", "").strip()
    target = parse_date(raw)
    if target is None:
        return {
            "status": "error",
            "message": f"Could not understand date '{raw}'. Use 'today', 'tomorrow', or YYYY-MM-DD.",
        }

    session_id = flow_manager.state["session_id"]
    redis = get_redis()

    # Slot scores encode date as days_from_today * 1000. Build a membership-only
    # ZSET for all slots on or after the target date, then let apply_filter
    # intersect it with any other active filters (same pattern as loc/prov/time).
    days = max(0, (target - date.today()).days)
    score_min = days * 1000
    base_key = f"session:{session_id}:slots"
    date_key = f"session:{session_id}:date:{target.isoformat()}"

    slot_ids = await redis.zrangebyscore(base_key, score_min, "+inf")
    if not slot_ids:
        return {
            "status": "no_slots",
            "message": f"No available slots on or after {target.isoformat()}.",
            "previous_options_still_available": True,
        }

    async with redis.pipeline(transaction=False) as pipe:
        for slot_id in slot_ids:
            pipe.zadd(date_key, {slot_id: 0})
        pipe.expire(date_key, SESSION_TTL)
        await pipe.execute()

    return await apply_filter(
        flow_manager,
        {"type": "date", "key": date_key, "label": target.strftime("%B %-d")},
    )


SCHEMA = FlowsFunctionSchema(
    name="filter_by_date",
    description=(
        "Show only slots on or after a specific date. "
        "Use when the caller says they want an appointment on a particular day or from a certain date onwards."
    ),
    properties={
        "date": {
            "type": "string",
            "description": (
                "The target date as 'today', 'tomorrow', or ISO format (YYYY-MM-DD). "
                "For 'after September 5th', pass '2026-09-05'."
            ),
        }
    },
    required=["date"],
    handler=_handler,
)