from pipecat_flows import FlowManager, FlowsFunctionSchema

from tools.filters._slot_helpers import apply_filter

_VALID_BUCKETS = {"morning", "afternoon", "evening"}


async def _handler(args: dict, flow_manager: FlowManager) -> dict:
    bucket = args.get("time_of_day", "").strip().lower()
    if bucket not in _VALID_BUCKETS:
        return {
            "status": "error",
            "message": f"time_of_day must be one of: {', '.join(sorted(_VALID_BUCKETS))}",
        }

    session_id = flow_manager.state["session_id"]
    return await apply_filter(
        flow_manager,
        {
            "type":  "time",
            "key":   f"session:{session_id}:time:{bucket}",
            "label": bucket,
        },
    )


SCHEMA = FlowsFunctionSchema(
    name="filter_by_time",
    description="Narrow available slots to a time of day (morning, afternoon, or evening).",
    properties={
        "time_of_day": {
            "type": "string",
            "enum": ["morning", "afternoon", "evening"],
            "description": "morning = before noon, afternoon = noon–5 PM, evening = after 5 PM.",
        }
    },
    required=["time_of_day"],
    handler=_handler,
)