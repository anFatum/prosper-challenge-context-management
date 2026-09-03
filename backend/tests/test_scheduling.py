from unittest.mock import AsyncMock, MagicMock, patch

from tests.conftest import make_row
from tools.scheduling.book_slot import _handler as book_slot_handler
from tools.scheduling.check_appointment_requirements import _handler as check_req_handler


# ── book_slot ─────────────────────────────────────────────────────────────────

async def test_book_slot_missing_slot_id_returns_error():
    fm = MagicMock()
    fm.state = {"slot_id": "", "session_id": "sess-1"}
    result = await book_slot_handler({}, fm)
    assert result["status"] == "error"


async def test_book_slot_conflict_when_already_taken(mock_pool):
    fm = MagicMock()
    fm.state = {"slot_id": "aaaaaaaa-0000-0000-0000-000000000001", "session_id": "sess-1"}
    mock_pool.execute = AsyncMock(return_value="UPDATE 0")

    with patch("tools.scheduling.book_slot.get_pool", return_value=mock_pool):
        result = await book_slot_handler({}, fm)

    assert result["status"] == "conflict"


async def test_book_slot_success(mock_pool):
    fm = MagicMock()
    fm.state = {"slot_id": "aaaaaaaa-0000-0000-0000-000000000001", "session_id": "sess-1"}
    mock_pool.execute = AsyncMock(return_value="UPDATE 1")

    with patch("tools.scheduling.book_slot.get_pool", return_value=mock_pool):
        result = await book_slot_handler({}, fm)

    assert result["status"] == "ok"


async def test_book_slot_calls_db_with_session_id(mock_pool):
    fm = MagicMock()
    fm.state = {"slot_id": "aaaaaaaa-0000-0000-0000-000000000001", "session_id": "sess-abc"}
    mock_pool.execute = AsyncMock(return_value="UPDATE 1")

    with patch("tools.scheduling.book_slot.get_pool", return_value=mock_pool):
        await book_slot_handler({}, fm)

    call_args = mock_pool.execute.call_args
    assert "sess-abc" in call_args.args


# ── check_appointment_requirements ───────────────────────────────────────────

async def test_check_requires_referral_no_new_patients(mock_pool):
    fm = MagicMock()
    fm.state = {"appointment_type_id": "appt_001"}
    mock_pool.fetchrow = AsyncMock(return_value=make_row(
        name="MRI Scan",
        requires_referral=True,
        new_patients_allowed=False,
    ))

    with patch("tools.scheduling.check_appointment_requirements.get_pool", return_value=mock_pool):
        result = await check_req_handler({}, fm)

    assert result["status"] == "success"
    assert result["requires_referral"] is True
    assert result["new_patients_allowed"] is False
    assert fm.state["requires_referral"] is True
    assert fm.state["new_patients_allowed"] is False


async def test_check_no_referral_accepts_new_patients(mock_pool):
    fm = MagicMock()
    fm.state = {"appointment_type_id": "appt_002"}
    mock_pool.fetchrow = AsyncMock(return_value=make_row(
        name="General Consultation",
        requires_referral=False,
        new_patients_allowed=True,
    ))

    with patch("tools.scheduling.check_appointment_requirements.get_pool", return_value=mock_pool):
        result = await check_req_handler({}, fm)

    assert result["status"] == "success"
    assert result["requires_referral"] is False
    assert result["new_patients_allowed"] is True


async def test_check_unknown_appointment_defaults_safe(mock_pool):
    """Unknown appointment_type_id must not crash — defaults to no referral required."""
    fm = MagicMock()
    fm.state = {"appointment_type_id": "appt_UNKNOWN"}
    mock_pool.fetchrow = AsyncMock(return_value=None)

    with patch("tools.scheduling.check_appointment_requirements.get_pool", return_value=mock_pool):
        result = await check_req_handler({}, fm)

    assert result["status"] == "success"
    assert result["requires_referral"] is False
    assert result["new_patients_allowed"] is True