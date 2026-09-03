from loguru import logger
from pipecat_flows import FlowManager, FlowsFunctionSchema

from db import get_pool
from tools.utils import resolve_id


async def _handler(args: dict, flow_manager: FlowManager) -> dict:
    query = args.get("name", "").strip()
    if not query:
        return {"status": "error", "message": "name is required"}

    pool = get_pool()
    loc_id = await resolve_id(query, "loc", pool)
    if not loc_id:
        logger.warning(f"lookup_location: no match for '{query}'")
        return {"status": "not_found", "query": query}

    row = await pool.fetchrow(
        "SELECT id, name, address, city, phone, hours, capabilities FROM locations WHERE id = $1",
        loc_id,
    )
    logger.info(f"lookup_location: '{query}' → {loc_id}")
    return {
        "status": "success",
        "id": row["id"],
        "name": row["name"],
        "address": row["address"],
        "city": row["city"],
        "phone": row["phone"] or "",
        "hours": row["hours"] or "",
        "capabilities": list(row["capabilities"] or []),
    }


SCHEMA = FlowsFunctionSchema(
    name="lookup_location",
    description=(
        "Look up a clinic location by name or ID. "
        "Use this when the caller asks about a specific location — its address, hours, phone, or services."
    ),
    properties={
        "name": {
            "type": "string",
            "description": "Location name (e.g. 'Mission Bay Health Center') or catalog ID (e.g. 'loc_001').",
        }
    },
    required=["name"],
    handler=_handler,
)