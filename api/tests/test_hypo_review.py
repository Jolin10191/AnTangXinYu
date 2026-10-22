"""低血糖 24 小时复盘的纯函数部分。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from antang_api.agents.core import render_core_system_prompt
from antang_api.psychosocial.hypo_review import (
    LOW_READING_MG_DL,
    render_hypo_review_prompt,
    review_is_due,
)


def test_low_reading_threshold_matches_guideline() -> None:
    assert LOW_READING_MG_DL == 70


def test_review_is_due_inside_the_window() -> None:
    now = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)

    assert review_is_due(now - timedelta(hours=1), now) is True
    assert review_is_due(now - timedelta(hours=23, minutes=59), now) is True


def test_review_is_not_due_after_the_window() -> None:
    now = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)

    assert review_is_due(now - timedelta(hours=25), now) is False


def test_review_is_not_due_for_future_readings() -> None:
    now = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)

    assert review_is_due(now + timedelta(minutes=5), now) is False


def test_prompt_asks_one_question_and_forbids_dosing_advice() -> None:
    prompt = render_hypo_review_prompt(reported_by_user=False)

    assert "补了什么" in prompt
    assert "胰岛素剂量" in prompt
    assert "一次只问一个问题" in prompt


def test_reported_and_automatic_openings_differ() -> None:
    automatic = render_hypo_review_prompt(reported_by_user=False)
    reported = render_hypo_review_prompt(reported_by_user=True)

    assert automatic != reported
    assert "你说的那次" in reported


def test_core_prompt_carries_the_review_only_when_asked() -> None:
    """复盘片段是逐轮附上的：没有该问的事件时，提示词里不能出现这个话题。"""

    without_review = render_core_system_prompt("档案")

    assert "[低血糖之后的复盘]" not in without_review

    review = render_hypo_review_prompt(reported_by_user=True)
    with_review = render_core_system_prompt("档案", hypo_review_context=review)

    assert with_review.endswith(review)
    assert "档案" in with_review
