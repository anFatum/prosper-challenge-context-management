from pipecat_flows import FlowManager, FlowsFunctionSchema

from db import get_pool
from tools.filters._slot_helpers import apply_filter
from tools.utils import resolve_id


async def _handler(args: dict, flow_manager: FlowManager) -> dict:
    provider_raw = args.get("provider", "").strip()
    if not provider_raw:
        return {"status": "error", "message": "provider is required"}

    prov_id = await resolve_id(provider_raw, "prov", get_pool())
    if not prov_id:
        return {"status": "error", "message": f"Provider '{provider_raw}' not found in catalog."}

    session_id = flow_manager.state["session_id"]
    return await apply_filter(
        flow_manager,
        {
            "type":  "provider",
            "key":   f"session:{session_id}:prov:{prov_id}",
            "label": provider_raw,
        },
    )


SCHEMA = FlowsFunctionSchema(
    name="filter_by_provider",
    description="Narrow available slots to a specific provider.",
    properties={
        "provider": {
            "type": "string",
            "description": "Provider name or ID (e.g. 'Dr. Martinez' or 'prov_012').",
        }
    },
    required=["provider"],
    handler=_handler,
)