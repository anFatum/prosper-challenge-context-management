from loguru import logger
from pipecat_flows import FlowManager, FlowsFunctionSchema

from db import get_pool


async def _handler(args: dict, flow_manager: FlowManager) -> dict:
    appt_id = flow_manager.state.get("appointment_type_id", "UNSPECIFIED")

    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT name, requires_referral, new_patients_allowed FROM appointment_types WHERE id = $1",
        appt_id,
    )

    if row is None:
        logger.warning(f"check_appointment_requirements: unknown appointment_type_id '{appt_id}'")
        requires_referral = False
        new_patients_allowed = True
        appt_name = "unknown appointment"
    else:
        requires_referral = bool(row["requires_referral"])
        new_patients_allowed = bool(row["new_patients_allowed"])
        appt_name = row["name"]

    flow_manager.state["requires_referral"] = requires_referral
    flow_manager.state["new_patients_allowed"] = new_patients_allowed
    flow_manager.state["appointment_type_name"] = appt_name
    logger.info(f"Referral check: {appt_name} requires_referral={requires_referral} new_patients_allowed={new_patients_allowed}")

    return {
        "status": "success",
        "appointment_type_name": appt_name,
        "requires_referral": requires_referral,
        "new_patients_allowed": new_patients_allowed,
    }


SCHEMA = FlowsFunctionSchema(
    name="check_appointment_requirements",
    description=(
        "Check whether the classified appointment type requires a referral and whether it accepts new patients. "
        "Call this at the start of the validate_appointment node before asking the patient anything."
    ),
    properties={},
    required=[],
    handler=_handler,
)