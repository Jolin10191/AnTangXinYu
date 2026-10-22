"""低血糖事件之后的 24 小时复盘。

复盘只问事实，不问感受，也不问「你为什么会低血糖」——归因容易被听成指责，
而补了什么、复测了没有、要不要调胰岛素，才是下一次真正用得上的东西。

三条边界：
- 只在事件发生后 24 小时内问一次，过期不再追；
- 不给胰岛素剂量建议（与红队的硬禁止项一致）；
- 用户说不想聊就停，不追问。
"""

from __future__ import annotations

from datetime import datetime, timedelta

LOW_READING_MG_DL = 70
REVIEW_WINDOW = timedelta(hours=24)

_AUTO_OPENING = "刚才那一次偏低之后，你后来补了什么？"
_REPORTED_OPENING = "你说的那次低血糖，后来补了什么、有没有再测一次？"

_FOLLOWUP = "补完之后大概多久复测的，那时是多少？"

_CLOSING = "要不要把这次记下来，下次再聊的时候我能记得？"


def review_is_due(occurred_at: datetime, now: datetime) -> bool:
    """事件是否还在可以复盘的窗口里（含 24 小时）。"""

    return timedelta(0) <= now - occurred_at <= REVIEW_WINDOW


def render_hypo_review_prompt(*, reported_by_user: bool) -> str:
    """渲染一次复盘用的提示词片段。

    只给一个问题；追问与收尾要等用户接上再用。
    """

    opening = _REPORTED_OPENING if reported_by_user else _AUTO_OPENING
    return "\n".join(
        [
            "[低血糖之后的复盘] 这是最近 24 小时内发生的一次偏低，还没有复盘过。",
            f"先只问一句：{opening}",
            f"如果用户愿意说，再问：{_FOLLOWUP}",
            f"收尾可以问：{_CLOSING}",
            "约束：不要问「为什么会低血糖」，不要给胰岛素剂量建议；"
            "一次只问一个问题，用户说不想聊就停。",
        ]
    )
