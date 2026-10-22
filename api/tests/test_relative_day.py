"""凌晨说的「明天」指哪一天。"""

from __future__ import annotations

from datetime import date, datetime, timezone

from antang_api.agents.relative_day import (
    DAY_BOUNDARY_HOUR,
    describe_today,
    is_late_night,
    resolve_relative_day,
    subjective_day,
)

TZ = timezone.utc


def _at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=TZ)


def test_boundary_hour_is_four() -> None:
    assert DAY_BOUNDARY_HOUR == 4


def test_after_midnight_still_belongs_to_previous_day() -> None:
    assert subjective_day(_at(20, 1, 12)) == date(2026, 10, 19)


def test_after_four_starts_a_new_day() -> None:
    assert subjective_day(_at(20, 4, 0)) == date(2026, 10, 20)


def test_evening_belongs_to_the_same_day() -> None:
    assert subjective_day(_at(20, 23, 30)) == date(2026, 10, 20)


def test_late_night_flag() -> None:
    assert is_late_night(_at(20, 1)) is True
    assert is_late_night(_at(20, 10)) is False


def test_tomorrow_ten_am_from_one_am_is_same_calendar_day() -> None:
    """10-20 01:12 说的「明天十点」，用户指的是 10-20 10:00。"""

    resolved = resolve_relative_day(_at(20, 1, 12), offset_days=1, offset_seconds=10 * 3600)

    assert resolved == _at(20, 10, 0)


def test_tomorrow_ten_am_from_ten_am_is_next_calendar_day() -> None:
    """白天说的「明天十点」就是真·次日。"""

    resolved = resolve_relative_day(_at(20, 10, 0), offset_days=1, offset_seconds=10 * 3600)

    assert resolved == _at(21, 10, 0)


def test_describe_today_warns_about_the_night_window() -> None:
    late = describe_today(_at(20, 1, 12))
    daytime = describe_today(_at(20, 10, 0))

    assert "熬夜" in late
    assert "2026-10-19" in late
    assert "熬夜" not in daytime
