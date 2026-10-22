"""检测"我答应了要在某个时间主动联系，但其实没有落成计划"。

线上真实发生过：助手说"明早 8:00 主动来找你"，用户第二天等了一整天，什么也没来，
第三天助手自己道歉说"后台没有真正把提醒定成功"。原因是这一轮根本没有调用计划工具——
模型只是在文字上做了一个承诺。

承诺不能靠提示词保证。这里用一个可测的判定：回复看起来像承诺，而这一轮没有任何
计划工具调用，就记一条警告。**只告警、不改写回复**：改写是另一种更糟的隐瞒，
会让用户以为提醒已经设好了。
"""

from __future__ import annotations

import re
from datetime import datetime

from antang_api.agents.relative_day import is_late_night, resolve_relative_day
from antang_api.tools.care_plan import CARE_PLAN_TOOL_NAME

__all__ = [
    "CARE_PLAN_TOOL_NAME",
    "CLOCK_PATTERN",
    "PROMISE_PATTERN",
    "promise_target",
    "promises_follow_up",
    "unbacked_promise",
]

# 「我会 / 到时 / 明早 / 今晚 / 待会」+ 24 字以内 + 「来找你 / 来问你 / 提醒你 / 主动找你」
PROMISE_PATTERN = re.compile(
    r"(我会|到时|明早|明天|今晚|待会|之后)[^。！？\n]{0,24}"
    r"(来找你|来问你|来问候|提醒你|主动找你|主动联系你|来关心你)"
)


def promises_follow_up(text: str) -> bool:
    """回复里是否承诺了一个未来的主动联系。"""

    return PROMISE_PATTERN.search(text) is not None


def unbacked_promise(text: str, tool_names: set[str] | list[str]) -> bool:
    """承诺了未来的主动联系，但这一轮没有调用计划工具。"""

    if not promises_follow_up(text):
        return False
    return CARE_PLAN_TOOL_NAME not in set(tool_names)


# 「十点 / 10 点 / 22:30 / 晚上八点」这类时刻说法。
CLOCK_PATTERN = re.compile(
    r"(?:(上午|下午|早上|明早|今晚|晚上|夜里|凌晨)\s*)?"
    r"([0-9]{1,2}|[一二两三四五六七八九十]{1,3})"
    r"\s*(?:[:：]\s*([0-9]{2})|点(?:半|([0-9]{1,2})分?)?)"
)

_CN_DIGITS = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def _cn_number(token: str) -> int | None:
    if token.isdigit():
        return int(token)
    if token in _CN_DIGITS:
        return _CN_DIGITS[token]
    if token.startswith("十") and len(token) == 2 and token[1] in _CN_DIGITS:
        return 10 + _CN_DIGITS[token[1]]
    if token.endswith("十") and len(token) == 2 and token[0] in _CN_DIGITS:
        return _CN_DIGITS[token[0]] * 10
    return None


def promise_target(
    text: str, *, now: datetime
) -> datetime | None:
    """把「明天十点来找你」换算成具体时刻。

    关键在「明天」按用户口中的明天算：凌晨一点说的明天是天亮以后那一天。
    算不出来、或者时刻已经过去，返回 None——守卫只对确定的情况告警。
    """

    promise = PROMISE_PATTERN.search(text)
    if promise is None:
        return None

    clock = CLOCK_PATTERN.search(text[: promise.start()] or text)
    if clock is None:
        clock = CLOCK_PATTERN.search(text[promise.start() :])
    if clock is None:
        return None

    hour = _cn_number(clock.group(2))
    if hour is None:
        return None

    minute = 0
    if clock.group(3):
        minute = int(clock.group(3))
    elif clock.group(4):
        minute = int(clock.group(4))
    elif clock.group(0).endswith("半"):
        minute = 30

    marker = clock.group(1) or ""
    if marker in {"下午", "晚上", "今晚", "夜里"} and hour < 12:
        hour += 12
    if marker == "凌晨" and hour >= 12:
        hour -= 12

    offset_days = 1 if ("明天" in text or "明早" in text) else 0
    # 「今晚」只有深夜说才指明天：凌晨一点说今晚七点，指的是天亮后的那个晚上；
    # 傍晚说今晚七点就是当天。按日历算会把傍晚的承诺整体推晚一天。
    if marker == "今晚" and is_late_night(now):
        offset_days = 1

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None

    resolved = resolve_relative_day(
        now, offset_days=offset_days, offset_seconds=hour * 3600 + minute * 60
    )
    if resolved <= now:
        return None
    return resolved
