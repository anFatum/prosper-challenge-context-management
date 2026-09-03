from loguru import logger
from pipecat_flows import FlowManager, FlowsFunctionSchema

from db import get_pool
from tools.utils import resolve_id


async def _handler(args: dict, flow_manager: FlowManager) -> dict:
    query = args.get("name", "").strip()
    if not query:
        return {"status": "error", "message": "name is required"}

    pool = get_pool()
    prov_id = await resolve_id(query, "prov", pool)
    if not prov_id:
        logger.warning(f"lookup_provider: no match for '{query}'")
        return {"status": "not_found", "query": query}

    row = await pool.fetchrow(
        "SELECT id, name, title, specialty, languages, accepting_new FROM providers WHERE id = $1",
        prov_id,
    )
    loc_rows = await pool.fetch(
        """
        SELECT l.id, l.name
        FROM locations l
        JOIN provider_locations pl ON pl.location_id = l.id
        WHERE pl.provider_id = $1
        ORDER BY l.name
        """,
        prov_id,
    )
    logger.info(f"lookup_provider: '{query}' → {prov_id}")
    return {
        "status": "success",
        "id": row["id"],
        "name": row["name"],
        "title": row["title"] or "",
        "specialty": row["specialty"] or "",
        "languages": list(row["languages"] or []),
        "location_ids": [r["id"] for r in loc_rows],
        "location_names": [r["name"] for r in loc_rows],
        "accepting_new_patients": bool(row["accepting_new"]),
    }


SCHEMA = FlowsFunctionSchema(
    name="lookup_provider",
    description=(
        "Look up a provider (doctor) by name or ID. "
        "Use this when the caller asks about a specific provider — their specialty, locations, languages, or availability for new patients."
    ),
    properties={
        "name": {
            "type": "string",
            "description": "Provider name (e.g. 'Dr. Chen') or catalog ID (e.g. 'prov_003').",
        }
    },
    required=["name"],
    handler=_handler,
)