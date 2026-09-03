from datetime import date, time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tools.filters._slot_helpers import (
    _composite_score,
    _fmt_time,
    _time_bucket,
    apply_filter,
)


# ── _time_bucket ──────────────────────────────────────────────────────────────

def test_time_bucket_morning():
    assert _time_bucket(time(0, 0)) == 0
    assert _time_bucket(time(9, 30)) == 0
    assert _time_bucket(time(11, 59)) == 0


def test_time_bucket_afternoon():
    assert _time_bucket(time(12, 0)) == 1
    assert _time_bucket(time(14, 0)) == 1
    assert _time_bucket(time(16, 59)) == 1


def test_time_bucket_evening():
    assert _time_bucket(time(17, 0)) == 2
    assert _time_bucket(time(20, 0)) == 2
    assert _time_bucket(time(23, 59)) == 2


# ── _composite_score ──────────────────────────────────────────────────────────

def test_score_earlier_date_is_lower():
    today = date.today()
    tomorrow = date.fromordinal(today.toordinal() + 1)
    assert _composite_score(today, time(9, 0), 0) < _composite_score(tomorrow, time(9, 0), 0)


def test_score_today_evening_beats_tomorrow_morning():
    today = date.today()
    tomorrow = date.fromordinal(today.toordinal() + 1)
    assert _composite_score(today, time(20, 0), 0) < _composite_score(tomorrow, time(9, 0), 0)


def test_score_morning_before_afternoon_same_day():
    today = date.today()
    assert _composite_score(today, time(9, 0), 0) < _composite_score(today, time(13, 0), 0)


def test_score_lower_provider_rank_wins():
    today = date.today()
    assert _composite_score(today, time(9, 0), 0) < _composite_score(today, time(9, 0), 1)


# ── _fmt_time ─────────────────────────────────────────────────────────────────

def test_fmt_time_morning():
    assert _fmt_time("09:30") == "9:30 AM"
    assert _fmt_time("08:00") == "8:00 AM"


def test_fmt_time_noon():
    assert _fmt_time("12:00") == "12:00 PM"


def test_fmt_time_afternoon():
    assert _fmt_time("13:00") == "1:00 PM"
    assert _fmt_time("16:45") == "4:45 PM"


def test_fmt_time_midnight():
    assert _fmt_time("00:00") == "12:00 AM"


# ── apply_filter ──────────────────────────────────────────────────────────────

async def test_apply_filter_empty_key_does_not_mutate_state():
    """When the filter key has no members, state must be unchanged."""
    fm = MagicMock()
    fm.state = {"session_id": "sess-1", "active_filters": [], "slot_cursor": 3}

    redis = AsyncMock()
    # First zcard: filter key is empty → bail out
    # Second zcard: base key (called inside recompute_current for still_available count)
    redis.zcard = AsyncMock(side_effect=[0, 5])

    with patch("db.redis.get_redis", return_value=redis):
        result = await apply_filter(fm, {
            "type": "location",
            "key": "session:sess-1:loc:loc_1",
            "label": "Downtown",
        })

    assert result["status"] == "no_slots"
    assert result["previous_options_still_available"] is True
    assert result["still_available_total"] == 5
    # State untouched
    assert fm.state["active_filters"] == []
    assert fm.state["slot_cursor"] == 3


async def test_apply_filter_combined_empty_does_not_mutate_state():
    """When a valid filter key combines to 0 results, state must be unchanged."""
    fm = MagicMock()
    fm.state = {"session_id": "sess-1", "active_filters": [], "slot_cursor": 3}

    redis = AsyncMock()
    # Filter key has members, so we proceed to intersection
    redis.zcard = AsyncMock(side_effect=[
        2,   # filter_entry key: non-empty
        0,   # current key after zinterstore: no combined results
        3,   # base key for still_available fallback
    ])
    redis.zinterstore = AsyncMock()
    redis.ttl = AsyncMock(return_value=900)
    redis.expire = AsyncMock()

    with patch("db.redis.get_redis", return_value=redis):
        result = await apply_filter(fm, {
            "type": "provider",
            "key": "session:sess-1:prov:prov_1",
            "label": "Dr. Chen",
        })

    assert result["status"] == "no_slots"
    assert result["previous_options_still_available"] is True
    # State untouched
    assert fm.state["active_filters"] == []
    assert fm.state["slot_cursor"] == 3