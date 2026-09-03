from loguru import logger
from pipecat_flows import FlowManager, FlowsFunctionSchema

from db import get_pool
from tools.utils import resolve_id


async def _handler(args: dict, flow_manager: FlowManager) -> dict:
    query = args.get("name", "").strip()
    if not query:
        return {"status": "error", "message": "name is required"}

    pool = get_pool()
    appt_id = await resolve_id(query, "appt", pool)
    if not appt_id:
        logger.warning(f"lookup_appointment_type: no match for '{query}'")
        return {"status": "not_found", "query": query}

    row = await pool.fetchrow(
        """
        SELECT id, name, specialty, duration_min, requires_referral,
               new_patients_allowed, required_capability
        FROM appointment_types WHERE id = $1
        """,
        appt_id,
    )
    logger.info(f"lookup_appointment_type: '{query}' → {appt_id}")
    return {
        "status": "success",
        "id": row["id"],
        "name": row["name"],
        "specialty": row["specialty"] or "",
        "duration_min": row["duration_min"],
        "requires_referral": bool(row["requires_referral"]),
        "new_patients_allowed": bool(row["new_patients_allowed"]),
        "required_capability": row["required_capability"],
    }


SCHEMA = FlowsFunctionSchema(
    name="lookup_appointment_type",
    description=(
        "Look up an appointment type by name or ID. "
        "Use this when the caller asks about a specific appointment — its duration, whether a referral is needed, or which locations offer it."
    ),
    properties={
        "name": {
            "type": "string",
            "description": "Appointment type name (e.g. 'Annual Physical') or catalog ID (e.g. 'appt_007').",
        }
    },
    required=["name"],
    handler=_handler,
)