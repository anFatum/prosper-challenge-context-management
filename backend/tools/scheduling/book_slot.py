from loguru import logger
from pipecat_flows import FlowManager, FlowsFunctionSchema

from db import get_pool


async def _handler(args: dict, flow_manager: FlowManager) -> dict:
    slot_id = flow_manager.state.get("slot_id", "").strip()
    session_id = flow_manager.state.get("session_id", "")

    if not slot_id:
        return {"status": "error", "message": "No slot selected."}

    pool = get_pool()
    # Optimistic lock: only mark unavailable if still available — one atomic UPDATE.
    result = await pool.execute(
        """
        UPDATE calendar_slots
           SET available  = FALSE,
               booked_at  = NOW(),
               session_id = $1
         WHERE id = $2::uuid
           AND available = TRUE
        """,
        session_id,
        slot_id,
    )
    rows_affected = int(result.split()[-1])  # "UPDATE N"

    if rows_affected == 0:
        logger.warning(f"book_slot: slot {slot_id} already taken")
        return {
            "status": "conflict",
            "message": "That slot was just taken by someone else. Please choose a different one.",
        }

    logger.info(f"book_slot: slot {slot_id} booked for session {session_id}")
    return {"status": "ok"}


SCHEMA = FlowsFunctionSchema(
    name="book_slot",
    description=(
        "Write the confirmed appointment to the database. "
        "Call this only after the patient has verbally confirmed the slot details. "
        "If it returns status conflict, apologise and call go_back to let them pick again."
    ),
    properties={},
    required=[],
    handler=_handler,
)
