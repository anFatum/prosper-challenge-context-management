from pipecat_flows import FlowManager, FlowsFunctionSchema

from db.redis import get_redis
from tools.filters._slot_helpers import get_options, recompute_current


async def _handler(args: dict, flow_manager: FlowManager) -> dict:
    session_id = flow_manager.state.get("session_id")
    if not session_id:
        return {"status": "error", "message": "No active session."}

    active_filters = flow_manager.state.get("active_filters", [])
    cursor = flow_manager.state.get("slot_cursor", 0)

    redis = get_redis()
    active_key, total = await recompute_current(session_id, active_filters, redis)

    if cursor >= total:
        return {"status": "end_of_results", "message": "No more slots available."}

    options = await get_options(session_id, active_key, cursor, redis)
    flow_manager.state["slot_cursor"] = cursor + len(options)

    return {
        "status": "ok",
        "total": total,
        "shown_so_far": flow_manager.state["slot_cursor"],
        "options": options,
    }


SCHEMA = FlowsFunctionSchema(
    name="get_next_options",
    description=(
        "Return the next 3 available slot options. "
        "Call when the caller asks to hear more or says none of the current options work."
    ),
    properties={},
    required=[],
    handler=_handler,
)