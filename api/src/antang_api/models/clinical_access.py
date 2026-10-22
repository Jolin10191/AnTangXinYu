"""统一查看密码与绑定个人登录会话的解锁凭证。"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from antang_api.database import Base


class ClinicalAccessSettings(Base):
    __tablename__ = "clinical_access_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_clinical_settings_singleton"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    revision: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    updated_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClinicalAccessSession(Base):
    __tablename__ = "clinical_access_sessions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=text("uuidv7()"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    login_session_id: Mapped[UUID] = mapped_column(ForeignKey("login_sessions.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    password_revision: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

