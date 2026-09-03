import json
from datetime import date

from pipecat_flows import FlowManager, FlowsFunctionSchema

from db import get_pool
from db.redis import get_redis
from tools.filters._slot_helpers import build_slot_store, get_options, parse_date, recompute_current, _fmt_time
from tools.utils import resolve_id


async def _handler(args: dict, flow_manager: FlowManager) -> dict:
    # Accept explicit arg or fall back to what classify_appointment stored
    appt_raw = (
        args.get("appointment_type_id", "").strip()
        or flow_manager.state.get("appointment_type_id", "")
    )
    if not appt_raw or appt_raw == "UNSPECIFIED":
        return {"status": "error", "message": "Appointment type not yet classified."}

    pool = get_pool()
    # appt_raw is always an ID at this point (set by classify_appointment_type);
    # only resolve if it looks like a name rather than an ID
    appt_type_id = appt_raw if appt_raw.startswith("appt_") else (
        await resolve_id(appt_raw, "appt", pool) or appt_raw
    )

    session_id = flow_manager.state["session_id"]
    redis = get_redis()

    total = await build_slot_store(session_id, appt_type_id, pool, redis)
    flow_manager.state["appointment_type_id"] = appt_type_id
    flow_manager.state["active_filters"] = []
    flow_manager.state["slot_cursor"] = 0

    if total == 0:
        return {
            "status": "no_slots",
            "message": "No available slots found for this appointment type.",
        }

    # Auto-apply any preferences the caller expressed before slot search began
    prefs: dict = flow_manager.state.get("user_preferences", {})
    # previous_provider is set by the is_returning_patient edge when new_patients_allowed=False
    if "previous_provider" in flow_manager.state and "provider" not in prefs:
        prefs = {**prefs, "provider": flow_manager.state["previous_provider"]}
    active_filters: list[dict] = []

    if "location" in prefs:
        loc_id = await resolve_id(prefs["location"], "loc", pool)
        if loc_id:
            active_filters.append({
                "type": "location",
                "key": f"session:{session_id}:loc:{loc_id}",
                "label": prefs["location"],
            })

    if "provider" in prefs:
        prov_id = await resolve_id(prefs["provider"], "prov", pool)
        if prov_id:
            active_filters.append({
                "type": "provider",
                "key": f"session:{session_id}:prov:{prov_id}",
                "label": prefs["provider"],
            })

    if "time_of_day" in prefs:
        bucket = prefs["time_of_day"].lower()
        if bucket in ("morning", "afternoon", "evening"):
            active_filters.append({
                "type": "time",
                "key": f"session:{session_id}:time:{bucket}",
                "label": bucket,
            })

    active_key, count = await recompute_current(session_id, active_filters, redis)

    # If preferences filter out everything, fall back to the full unfiltered set
    # rather than dead-ending — the caller can refine with explicit filter tools.
    preference_not_matched: list[str] = []
    if count == 0 and active_filters:
        preference_not_matched = [f["label"] for f in active_filters]
        active_filters = []
        active_key, count = await recompute_current(session_id, [], redis)

    # Apply date preference via score-range query — no per-date Redis key needed.
    # Slot scores encode the date as days_from_today * 1000, so a single day's
    # slots always fall within [days*1000, days*1000+999].
    date_options: list[dict] | None = None
    if "date" in prefs:
        target = parse_date(prefs["date"])
        if target is not None:
            days = max(0, (target - date.today()).days)
            score_min = days * 1000
            score_max = days * 1000 + 999
            date_slot_ids = await redis.zrangebyscore(active_key, score_min, score_max, start=0, num=3)
            if date_slot_ids:
                data_key = f"session:{session_id}:slot_data"
                raw = await redis.hmget(data_key, *date_slot_ids)
                date_options = []
                for slot_id, r in zip(date_slot_ids, raw):
                    if r is None:
                        continue
                    d = json.loads(r)
                    title = f" ({d['provider_title']})" if d["provider_title"] else ""
                    date_options.append({
                        "slot_id": slot_id,
                        "provider": f"{d['provider_name']}{title}",
                        "location": d["location_name"],
                        "date": d["date"],
                        "time": f"{_fmt_time(d['start_time'])} – {_fmt_time(d['end_time'])}",
                    })
            else:
                preference_not_matched.append(prefs["date"])

    options = date_options if date_options is not None else await get_options(session_id, active_key, 0, redis)
    flow_manager.state["active_filters"] = active_filters
    flow_manager.state["slot_cursor"] = len(options)

    result: dict = {"status": "ok", "total": count, "options": options}
    if active_filters:
        result["applied_preferences"] = [f["label"] for f in active_filters]
    if preference_not_matched:
        result["preference_not_matched"] = preference_not_matched
        result["preference_note"] = (
            f"No slots found for {', '.join(preference_not_matched)}. "
            "Showing all available options instead."
        )
    return result


SCHEMA = FlowsFunctionSchema(
    name="init_slot_search",
    description=(
        "Start slot search for the classified appointment type. "
        "Loads all eligible available slots into the session store and returns the first 3 options. "
        "Any preferences the caller mentioned earlier are applied automatically."
    ),
    properties={
        "appointment_type_id": {
            "type": "string",
            "description": "The ID returned by classify_appointment_type (e.g. 'appt_007'). "
                           "If omitted, the value already in session state is used.",
        }
    },
    required=[],
    handler=_handler,
)