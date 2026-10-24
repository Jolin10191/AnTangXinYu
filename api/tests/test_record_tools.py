"""记录工具：时间口径、必填项，以及它们确实注册进了 Agent 的工具集。"""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from antang_api.chat import TOOL_ACTIVITY_PHASES
from antang_api.tools.records import (
    RECORD_MEAL_TOOL_NAME,
    RECORD_MEDICATION_TOOL_NAME,
    MealRequest,
    MedicationRequest,
    _check_event_time,
    build_record_tools,
)

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)


def test_both_recording_tools_are_registered() -> None:
    assert TOOL_ACTIVITY_PHASES[RECORD_MEAL_TOOL_NAME] == "organizing"
    assert TOOL_ACTIVITY_PHASES[RECORD_MEDICATION_TOOL_NAME] == "organizing"

    tools = build_record_tools()
    assert [tool.name for tool in tools] == [
        RECORD_MEAL_TOOL_NAME,
        RECORD_MEDICATION_TOOL_NAME,
    ]


def test_a_time_that_has_not_happened_yet_is_refused() -> None:
    with pytest.raises(ValueError, match="还没到"):
        _check_event_time(NOW + timedelta(minutes=3), NOW)
    # 手机时钟会差一两分钟，两分钟以内放行
    assert _check_event_time(NOW + timedelta(minutes=1), NOW) == NOW + timedelta(
        minutes=1
    )


def test_a_backfill_older_than_a_month_is_refused() -> None:
    with pytest.raises(ValueError, match="最近 30 天"):
        _check_event_time(NOW - timedelta(days=31), NOW)
    assert _check_event_time(NOW - timedelta(days=29), NOW) == NOW - timedelta(days=29)


def test_a_time_without_a_timezone_is_refused() -> None:
    with pytest.raises(ValueError, match="带时区"):
        _check_event_time(datetime(2026, 10, 24, 10, 0), NOW)


def test_an_afternoon_record_of_a_morning_dose_keeps_the_morning_time() -> None:
    morning = datetime(2026, 10, 24, 10, 0, tzinfo=UTC)

    request = MedicationRequest(name="门冬胰岛素", dose_text="6 单位", taken_at=morning)

    assert request.taken_at == morning


def test_a_medication_without_a_dose_is_refused() -> None:
    with pytest.raises(ValidationError):
        MedicationRequest(name="二甲双胍", taken_at=NOW)  # pyright: ignore[reportCallIssue]


def test_a_meal_may_omit_the_carbs_the_patient_did_not_mention() -> None:
    request = MealRequest(meal_type="lunch", eaten_at=NOW, description="一碗面条")

    assert request.carbs_grams is None


def test_meal_carbs_outside_a_plausible_range_are_refused() -> None:
    with pytest.raises(ValidationError):
        MealRequest(meal_type="lunch", eaten_at=NOW, description="火锅", carbs_grams=500)
