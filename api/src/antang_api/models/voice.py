"""从声音里读出来的粗状态。

只存标量、不存音频：这条记录的意义是「这句话是脱口而出的，还是斟酌过的」，
不是留档。所以它可以过期，过期之后就不再被读取；它也不进用户可见的界面，
只用来决定这一轮该怎么说话。
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from antang_api.database import Base

SPEECH_PACES: tuple[str, ...] = ("slow", "normal", "fast", "unknown")
SPEECH_ENERGIES: tuple[str, ...] = ("low", "normal", "high", "unknown")
SPEECH_BREATHING: tuple[str, ...] = ("audible", "none", "unknown")

_PACES_SQL = ", ".join(f"'{value}'" for value in SPEECH_PACES)
_ENERGIES_SQL = ", ".join(f"'{value}'" for value in SPEECH_ENERGIES)
_BREATHING_SQL = ", ".join(f"'{value}'" for value in SPEECH_BREATHING)


class SpeechCue(Base):
    __tablename__ = "speech_cues"
    __table_args__ = (
        CheckConstraint(f"pace IN ({_PACES_SQL})", name="ck_speech_cue_pace"),
        CheckConstraint(f"energy IN ({_ENERGIES_SQL})", name="ck_speech_cue_energy"),
        CheckConstraint(
            f"breathing IN ({_BREATHING_SQL})", name="ck_speech_cue_breathing"
        ),
        CheckConstraint(
            "confidence BETWEEN 0 AND 1", name="ck_speech_cue_confidence"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("uuidv7()")
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    pace: Mapped[str] = mapped_column(String(16), server_default=text("'unknown'"))
    energy: Mapped[str] = mapped_column(String(16), server_default=text("'unknown'"))
    breathing: Mapped[str] = mapped_column(
        String(16), server_default=text("'unknown'")
    )
    # 模型自己的置信度，原样存：低置信是信息，不是要抹掉的噪声。
    confidence: Mapped[float] = mapped_column(Float)
    model_name: Mapped[str] = mapped_column(String(64))
    # 声音只对紧接着的那一句话有意义。房间里换了话题再拿二十分钟前的声音状态
    # 去解释，就是编故事。
    heard_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # 被某一轮对话读走之后打上时间戳，同一条不会被两轮共用。
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
