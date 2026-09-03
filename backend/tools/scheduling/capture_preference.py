from loguru import logger
from pipecat_flows import FlowManager, FlowsFunctionSchema

_VALID_TYPES = {"location", "provider", "time_of_day", "language", "date"}


async def _handler(args: dict, flow_manager: FlowManager) -> dict:
    pref_type = args.get("type", "").strip()
    pref_value = args.get("value", "").strip()

    if pref_type not in _VALID_TYPES:
        return {"status": "error", "message": f"Unknown preference type '{pref_type}'. Valid: {sorted(_VALID_TYPES)}"}
    if not pref_value:
        return {"status": "error", "message": "value is required"}

    prefs = flow_manager.state.setdefault("user_preferences", {})
    prefs[pref_type] = pref_value
    logger.info(f"capture_preference: {pref_type}='{pref_value}'")
    return {"status": "saved", "type": pref_type, "value": pref_value}


SCHEMA = FlowsFunctionSchema(
    name="capture_preference",
    description=(
        "Save a caller preference expressed before slot search begins. "
        "Call this whenever the caller mentions a preferred location, provider, time of day, or language — "
        "even before the appointment type is classified. "
        "The preference will be applied automatically when availability is searched."
    ),
    properties={
        "type": {
            "type": "string",
            "enum": ["location", "provider", "time_of_day", "language", "date"],
            "description": (
                "'location' — preferred clinic location or city; "
                "'provider' — preferred doctor by name; "
                "'time_of_day' — 'morning', 'afternoon', or 'evening'; "
                "'language' — preferred language spoken by provider; "
                "'date' — a specific date expressed as 'today', 'tomorrow', or an ISO date like '2026-09-05'."
            ),
        },
        "value": {
            "type": "string",
            "description": (
                "The preference value. For 'date': use 'today', 'tomorrow', or ISO format (YYYY-MM-DD). "
                "For others: the caller's own words (e.g. 'Mission Bay', 'Dr. Chen', 'morning', 'Spanish')."
            ),
        },
    },
    required=["type", "value"],
    handler=_handler,
)
