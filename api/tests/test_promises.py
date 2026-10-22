from datetime import datetime, timezone

from antang_api.agents.promises import (
    CARE_PLAN_TOOL_NAME,
    promise_target,
    promises_follow_up,
    unbacked_promise,
)


def _utc(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=timezone.utc)


def test_detects_a_promised_check_in() -> None:
    assert promises_follow_up("好，我会在明早 8:00 主动来找你，问问昨晚睡得怎么样。")


def test_detects_shorter_phrasings() -> None:
    assert promises_follow_up("那我今晚 9 点来问你。")
    assert promises_follow_up("到时我来问候你一声。")


def test_ignores_generic_offers() -> None:
    assert not promises_follow_up("你想聊的时候随时来找我。")
    assert not promises_follow_up("你可以自己定个闹钟，八点提醒你。")


def test_flags_a_promise_without_the_plan_tool() -> None:
    reply = "好，我会在明早 8:00 主动来找你。"
    assert unbacked_promise(reply, set())
    assert unbacked_promise(reply, {"search_diabetes_knowledge"})


def test_accepts_a_promise_backed_by_the_plan_tool() -> None:
    reply = "好，我会在明早 8:00 主动来找你。"
    assert not unbacked_promise(reply, {CARE_PLAN_TOOL_NAME})


def test_ignores_replies_without_a_promise() -> None:
    assert not unbacked_promise("先把糖块放手边，十五分钟后再测一次。", set())


# 凌晨说的「明天」是用户口中的明天：天亮以后那一天，不是日历上的次日。
def test_late_night_tomorrow_means_after_sunrise() -> None:
    target = promise_target("好，明天十点我来找你。", now=_utc(20, 1, 12))

    assert target == _utc(20, 10, 0)


def test_daytime_tomorrow_is_the_next_calendar_day() -> None:
    target = promise_target("好，明天十点我来找你。", now=_utc(20, 10, 0))

    assert target == _utc(21, 10, 0)


# 傍晚说「今晚九点」是当天；只有深夜说的「今晚」才落到第二天。
def test_evening_tonight_stays_on_the_same_day() -> None:
    target = promise_target("那我今晚九点来问你。", now=_utc(20, 18, 0))

    assert target == _utc(20, 21, 0)


def test_late_night_tonight_means_the_coming_evening() -> None:
    target = promise_target("那我今晚九点来问你。", now=_utc(20, 1, 0))

    assert target == _utc(20, 21, 0)


def test_a_clock_time_already_past_is_not_a_promise() -> None:
    assert promise_target("我会十点来问你。", now=_utc(20, 11, 0)) is None


def test_a_reply_without_a_clock_time_returns_none() -> None:
    assert promise_target("你还好吗？", now=_utc(20, 11, 0)) is None
