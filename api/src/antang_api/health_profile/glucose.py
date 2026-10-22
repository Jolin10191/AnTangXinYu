"""血糖记录的读写与撤回。

只做存取与最基础的汇总，不做任何临床判断：什么算低、什么时候该提醒，
都在别处按阈值决定，这里只负责把数字和时间如实保存。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from antang_api.models.glucose import GlucoseReading


async def record_glucose_reading(
    session: AsyncSession,
    *,
    user_id: UUID,
    value_mg_dl: int,
    measured_at: datetime,
    context: str = "other",
    source: str = "manual",
    note: str | None = None,
) -> GlucoseReading:
    reading = GlucoseReading(
        user_id=user_id,
        value_mg_dl=value_mg_dl,
        measured_at=measured_at,
        context=context,
        source=source,
        note=note,
    )
    session.add(reading)
    await session.flush()
    return reading


async def list_glucose_readings(
    session: AsyncSession,
    *,
    user_id: UUID,
    days: int = 14,
    limit: int = 200,
) -> list[GlucoseReading]:
    """按时间倒序返回未撤回的读数。"""

    since = datetime.now(UTC) - timedelta(days=days)
    result = await session.scalars(
        select(GlucoseReading)
        .where(
            GlucoseReading.user_id == user_id,
            GlucoseReading.revoked_at.is_(None),
            GlucoseReading.measured_at >= since,
        )
        .order_by(GlucoseReading.measured_at.desc())
        .limit(limit)
    )
    return list(result)


async def revoke_glucose_reading(
    session: AsyncSession,
    *,
    user_id: UUID,
    reading_id: UUID,
) -> GlucoseReading | None:
    """撤回一条读数：打标记，不删行。

    撤回后数据不再被读取，但"记过又撤回"这件事本身保留下来——对低血糖恐惧
    来说，撤回行为是回避的一部分，删干净反而看不见。
    """

    reading = await session.scalar(
        select(GlucoseReading).where(
            GlucoseReading.id == reading_id,
            GlucoseReading.user_id == user_id,
            GlucoseReading.revoked_at.is_(None),
        )
    )
    if reading is None:
        return None
    reading.revoked_at = datetime.now(UTC)
    await session.flush()
    return reading


async def summarize_glucose(
    session: AsyncSession,
    *,
    user_id: UUID,
    days: int = 7,
) -> dict[str, object]:
    """窗口内的读数统计。低于 70 mg/dL 的条数单独给出，供界面展示。"""

    since = datetime.now(UTC) - timedelta(days=days)
    row = (
        await session.execute(
            select(
                func.count(GlucoseReading.id),
                func.avg(GlucoseReading.value_mg_dl),
                func.min(GlucoseReading.value_mg_dl),
                func.max(GlucoseReading.value_mg_dl),
                func.count(GlucoseReading.id).filter(GlucoseReading.value_mg_dl < 70),
            ).where(
                GlucoseReading.user_id == user_id,
                GlucoseReading.revoked_at.is_(None),
                GlucoseReading.measured_at >= since,
            )
        )
    ).one()

    count = int(row[0] or 0)
    return {
        "days": days,
        "count": count,
        "average_mg_dl": round(float(row[1]), 1) if row[1] is not None else None,
        "minimum_mg_dl": int(row[2]) if row[2] is not None else None,
        "maximum_mg_dl": int(row[3]) if row[3] is not None else None,
        "below_70_count": int(row[4] or 0),
    }


async def pending_hypo_review(
    session: AsyncSession,
    *,
    user_id: UUID,
    now: datetime,
    low_mg_dl: int = 70,
    window: timedelta = timedelta(hours=24),
) -> GlucoseReading | None:
    """找出还在复盘窗口里、且没问过的那一条偏低记录。

    只取最近一条：同一次事件问第二遍比不问更伤人，两条记录连着问更像审问。
    """

    statement = (
        select(GlucoseReading)
        .where(
            GlucoseReading.user_id == user_id,
            GlucoseReading.revoked_at.is_(None),
            GlucoseReading.reviewed_at.is_(None),
            GlucoseReading.value_mg_dl < low_mg_dl,
            GlucoseReading.measured_at >= now - window,
            GlucoseReading.measured_at <= now,
        )
        .order_by(GlucoseReading.measured_at.desc())
        .limit(1)
    )
    return await session.scalar(statement)


async def mark_hypo_reviewed(
    session: AsyncSession, *, reading: GlucoseReading, now: datetime
) -> None:
    """标记这次偏低已经复盘过，避免反复追问。"""

    reading.reviewed_at = now
    await session.commit()
