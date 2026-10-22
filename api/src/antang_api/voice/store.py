"""声音状态的存取。

三个动作：记一条、取一条还没被用过的、用完之后打上时间戳。都不提交事务，
由调用方决定——转写路由自己提交，对话则和回答写在同一个事务里，这样一次
失败的回复不会把声音状态白白消耗掉。
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from antang_api.models import SpeechCue
from antang_api.voice.speech_cue import SPEECH_CUE_WINDOW_SECONDS, SpeechCueData


async def record_speech_cue(
    session: AsyncSession,
    *,
    user_id: UUID,
    cue: SpeechCueData,
    model_name: str,
    now: datetime | None = None,
) -> SpeechCue:
    heard_at = now or datetime.now(UTC)
    row = SpeechCue(
        user_id=user_id,
        pace=cue.pace,
        energy=cue.energy,
        breathing=cue.breathing,
        confidence=cue.confidence,
        model_name=model_name[:64],
        heard_at=heard_at,
        expires_at=heard_at + timedelta(seconds=SPEECH_CUE_WINDOW_SECONDS),
    )
    session.add(row)
    return row


async def pending_speech_cue(
    session: AsyncSession,
    *,
    user_id: UUID,
    now: datetime | None = None,
) -> SpeechCue | None:
    """取最近一条还没被用过、也还没过期的声音状态。"""

    moment = now or datetime.now(UTC)
    return await session.scalar(
        select(SpeechCue)
        .where(
            SpeechCue.user_id == user_id,
            SpeechCue.consumed_at.is_(None),
            SpeechCue.expires_at > moment,
        )
        .order_by(SpeechCue.heard_at.desc(), SpeechCue.id)
        .limit(1)
    )


async def mark_speech_cue_consumed(
    session: AsyncSession,
    *,
    cue_id: UUID,
    now: datetime | None = None,
) -> None:
    """标记这一条已经被某一轮对话读走。不提交，跟回答同一个事务。"""

    row = await session.get(SpeechCue, cue_id)
    if row is not None and row.consumed_at is None:
        row.consumed_at = now or datetime.now(UTC)


def as_speech_cue_data(row: SpeechCue) -> SpeechCueData:
    """把数据库行还原成解析层的值对象。"""

    return SpeechCueData(
        pace=row.pace,
        energy=row.energy,
        breathing=row.breathing,
        confidence=float(row.confidence),
    )
