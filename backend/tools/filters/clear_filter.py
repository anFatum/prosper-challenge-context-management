from pipecat_flows import FlowManager, FlowsFunctionSchema

from db.redis import get_redis
from tools.filters._slot_helpers import get_options, recompute_current

_VALID_TYPES = {"location", "provider", "time", "all"}


async def _handler(args: dict, flow_manager: FlowManager) -> dict:
    filter_type = args.get("filter_type", "all").strip().lower()
    if filter_type not in _VALID_TYPES:
        return {
            "status": "error",
            "message": f"filter_type must be one of: {', '.join(sorted(_VALID_TYPES))}",
        }

    session_id = flow_manager.state.get("session_id")
    if not session_id:
        return {"status": "error", "message": "No active session."}

    active_filters: list[dict] = list(flow_manager.state.get("active_filters", []))

    if filter_type == "all":
        active_filters = []
    else:
        active_filters = [f for f in active_filters if f["type"] != filter_type]

    redis = get_redis()
    active_key, total = await recompute_current(session_id, active_filters, redis)
    options = await get_options(session_id, active_key, 0, redis)

    flow_manager.state["active_filters"] = active_filters
    flow_manager.state["slot_cursor"] = len(options)

    return {"status": "ok", "total": total, "options": options}


SCHEMA = FlowsFunctionSchema(
    name="clear_filter",
    description="Remove one or all active slot filters and return fresh options.",
    properties={
        "filter_type": {
            "type": "string",
            "enum": ["location", "provider", "time", "all"],
            "description": "Which filter to remove. Use 'all' to reset completely.",
        }
    },
    required=["filter_type"],
    handler=_handler,
)