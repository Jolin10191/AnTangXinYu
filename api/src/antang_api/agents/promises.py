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

from antang_api.tools.care_plan import CARE_PLAN_TOOL_NAME

__all__ = [
    "CARE_PLAN_TOOL_NAME",
    "PROMISE_PATTERN",
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
