"""用户口中的「今天」「明天」按什么算。

熬夜求助的人，凌晨一点说的「明天」几乎总是指天亮以后的那一天，
不是日历上的次日。如果按日历算，十点二十凌晨 1:12 说的「明天十点」
会排到 10-21 十点——晚了整整一天，病人等不到人。

所以这里按「睡眠日」划分：凌晨到 4 点算作前一天的延续，
4 点之后才进入新的一天。4 点是惯例值（睡眠研究里常用），
不做成配置项：多一个开关就多一种线上不一致。
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

# 4 点之前仍算前一天的延续。
DAY_BOUNDARY_HOUR = 4


def subjective_day(moment: datetime) -> date:
    """这一刻对用户来说属于哪一天。"""

    return (moment - timedelta(hours=DAY_BOUNDARY_HOUR)).date()


def is_late_night(moment: datetime) -> bool:
    """是否处在「跨夜的凌晨」——承诺措辞要不要改就看这个。"""

    return moment.hour < DAY_BOUNDARY_HOUR


def resolve_relative_day(
    moment: datetime,
    *,
    offset_days: int,
    offset_seconds: int | None = None,
) -> datetime:
    """把「明天/后天」换算成一个具体时刻。

    offset_days 以用户的「今天」为 0；offset_seconds 是当天从 0 点起的秒数。
    返回带时区的具体时刻，保持与输入相同的时区。
    """

    base = subjective_day(moment) + timedelta(days=offset_days)
    seconds = offset_seconds or 0
    resolved = datetime.combine(base, time.min, tzinfo=moment.tzinfo) + timedelta(
        seconds=seconds
    )
    return resolved


def describe_today(moment: datetime) -> str:
    """给提示词用的一句话，说明现在对用户算哪一天。

    凌晨不解释的话，模型会把「明天」算成次日，承诺直接晚一天。
    """

    today = subjective_day(moment)
    if is_late_night(moment):
        return (
            f"用户本地时间是 {moment.isoformat()}，属于熬夜时段："
            f"在用户口中「今天」仍然指 {today.isoformat()}（也就是天亮以后），"
            "「明天」指再往后一天。"
        )
    return f"用户本地时间是 {moment.isoformat()}，用户口中的「今天」是 {today.isoformat()}。"
