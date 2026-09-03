from pipecat_flows import FlowManager, FlowsFunctionSchema

from db import get_pool
from tools.filters._slot_helpers import apply_filter
from tools.utils import resolve_id


async def _handler(args: dict, flow_manager: FlowManager) -> dict:
    location_raw = args.get("location", "").strip()
    if not location_raw:
        return {"status": "error", "message": "location is required"}

    loc_id = await resolve_id(location_raw, "loc", get_pool())
    if not loc_id:
        return {"status": "error", "message": f"Location '{location_raw}' not found in catalog."}

    session_id = flow_manager.state["session_id"]
    return await apply_filter(
        flow_manager,
        {
            "type":  "location",
            "key":   f"session:{session_id}:loc:{loc_id}",
            "label": location_raw,
        },
    )


SCHEMA = FlowsFunctionSchema(
    name="filter_by_location",
    description="Narrow available slots to a specific clinic location.",
    properties={
        "location": {
            "type": "string",
            "description": "Location name or ID (e.g. 'Downtown Clinic' or 'loc_003').",
        }
    },
    required=["location"],
    handler=_handler,
)
