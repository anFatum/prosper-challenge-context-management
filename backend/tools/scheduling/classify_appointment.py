from loguru import logger
from openai import AsyncOpenAI
from pipecat_flows import FlowManager, FlowsFunctionSchema

from db import get_pool

_SYSTEM_PROMPT = """\
You are a medical appointment classifier.
Given a caller's free-text description of the appointment they want, return ONLY the
appointment type ID (e.g. "appt_007") that best matches from the list below.
If nothing matches with reasonable confidence, return the single word UNSPECIFIED.
Do not explain. Do not add punctuation. Return exactly one token.

Available appointment types:
{types_list}"""

_openai: AsyncOpenAI | None = None
_appt_types_list: str | None = None  # cached after first DB fetch


def _client() -> AsyncOpenAI:
    global _openai
    if _openai is None:
        _openai = AsyncOpenAI()
    return _openai


async def _get_types_list() -> str:
    global _appt_types_list
    if _appt_types_list is None:
        pool = get_pool()
        rows = await pool.fetch(
            "SELECT id, name, specialty FROM appointment_types ORDER BY id"
        )
        _appt_types_list = "\n".join(
            f"{r['id']}: {r['name']} ({r['specialty'] or 'General'})"
            for r in rows
        )
    return _appt_types_list


async def _handler(args: dict, flow_manager: FlowManager) -> dict:
    description = args.get("description", "")
    types_list = await _get_types_list()
    content = _SYSTEM_PROMPT.format(types_list=types_list)
    logger.info(f"Classifying appointment type: {description}")
    try:
        response = await _client().chat.completions.create(
            model="gpt-5-nano",
            messages=[
                {"role": "system", "content": content},
                {"role": "user", "content": description},
            ],
            max_completion_tokens=512,
        )
        cached = response.usage.prompt_tokens_details.cached_tokens if response.usage else 0
        logger.info(
            f"Classify usage — prompt: {response.usage.prompt_tokens}, "
            f"cached: {cached}, completion: {response.usage.completion_tokens}"
        )
        result = response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"classify_appointment_type failed: {e}")
        flow_manager.state["appointment_type_id"] = "ERROR"
        return {"status": "error", "appointment_type_id": "ERROR"}

    # Validate the returned ID and fetch requirements in the same query
    appt_name = ""
    requires_referral = False
    new_patients_allowed = True
    if result != "UNSPECIFIED":
        pool = get_pool()
        row = await pool.fetchrow(
            "SELECT id, name, requires_referral, new_patients_allowed FROM appointment_types WHERE id = $1",
            result,
        )
        if row is None:
            logger.warning(f"Classifier returned unknown id '{result}', falling back to UNSPECIFIED")
            result = "UNSPECIFIED"
        else:
            appt_name            = row["name"]
            requires_referral    = row["requires_referral"]
            new_patients_allowed = row["new_patients_allowed"]

    flow_manager.state["appointment_type_id"]   = result
    flow_manager.state["requires_referral"]      = requires_referral
    flow_manager.state["new_patients_allowed"]   = new_patients_allowed
    logger.info(f"Appointment type classified as: {result} '{appt_name}' "
                f"(referral={requires_referral}, new_patients={new_patients_allowed})")
    return {
        "status": "success",
        "appointment_type_id": result,
        "appointment_type_name": appt_name,
        "requires_referral": requires_referral,
        "new_patients_allowed": new_patients_allowed,
    }


SCHEMA = FlowsFunctionSchema(
    name="classify_appointment_type",
    description="Classify the caller's description into a catalog appointment type and store it in session state.",
    properties={
        "description": {
            "type": "string",
            "description": "The caller's own words describing the appointment they need.",
        }
    },
    required=["description"],
    handler=_handler,
)