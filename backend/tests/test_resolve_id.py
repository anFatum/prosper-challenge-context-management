from unittest.mock import AsyncMock, MagicMock, call

import pytest

from tests.conftest import make_row
from tools.utils import resolve_id


async def test_empty_string_returns_none_without_db_call(mock_pool):
    result = await resolve_id("", "prov", mock_pool)
    assert result is None
    mock_pool.fetchrow.assert_not_called()
    mock_pool.fetch.assert_not_called()


async def test_whitespace_only_returns_none(mock_pool):
    result = await resolve_id("   ", "prov", mock_pool)
    assert result is None


async def test_unknown_prefix_raises():
    mock_pool = MagicMock()
    with pytest.raises(ValueError, match="Unknown prefix"):
        await resolve_id("anything", "bad", mock_pool)


async def test_exact_match_returns_id_without_further_passes(mock_pool):
    mock_pool.fetchrow = AsyncMock(return_value=make_row(id="prov_001"))

    result = await resolve_id("Dr. Chen", "prov", mock_pool)

    assert result == "prov_001"
    mock_pool.fetch.assert_not_called()          # substring pass skipped
    assert mock_pool.fetchrow.call_count == 1    # only exact pass


async def test_substring_fallback_when_exact_fails(mock_pool):
    mock_pool.fetchrow = AsyncMock(return_value=None)  # exact fails
    mock_pool.fetch = AsyncMock(return_value=[make_row(id="prov_002")])

    result = await resolve_id("chen", "prov", mock_pool)

    assert result == "prov_002"
    assert mock_pool.fetch.call_count == 1
    # Fuzzy fetchrow should not be called (substring already matched)
    assert mock_pool.fetchrow.call_count == 1


async def test_fuzzy_fallback_when_exact_and_substring_fail(mock_pool):
    mock_pool.fetchrow = AsyncMock(side_effect=[
        None,                       # exact pass → no match
        make_row(id="prov_003"),    # fuzzy pass → match
    ])
    mock_pool.fetch = AsyncMock(return_value=[])  # substring → empty

    result = await resolve_id("ramirez", "prov", mock_pool)

    assert result == "prov_003"
    assert mock_pool.fetchrow.call_count == 2
    assert mock_pool.fetch.call_count == 1


async def test_no_match_returns_none(mock_pool):
    mock_pool.fetchrow = AsyncMock(return_value=None)
    mock_pool.fetch = AsyncMock(return_value=[])

    result = await resolve_id("zzznomatch", "prov", mock_pool)

    assert result is None
    assert mock_pool.fetchrow.call_count == 2    # exact + fuzzy both tried
    assert mock_pool.fetch.call_count == 1       # substring tried


async def test_resolves_location_prefix(mock_pool):
    mock_pool.fetchrow = AsyncMock(return_value=make_row(id="loc_001"))

    result = await resolve_id("Downtown Clinic", "loc", mock_pool)

    assert result == "loc_001"
    # Verify the query targeted the locations table
    sql = mock_pool.fetchrow.call_args.args[0]
    assert "locations" in sql


async def test_resolves_appointment_prefix(mock_pool):
    mock_pool.fetchrow = AsyncMock(return_value=make_row(id="appt_007"))

    result = await resolve_id("Annual Physical", "appt", mock_pool)

    assert result == "appt_007"
    sql = mock_pool.fetchrow.call_args.args[0]
    assert "appointment_types" in sql