from datetime import datetime
from uuid import UUID, uuid4
from enum import StrEnum
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Uuid, func, true
from sqlalchemy.orm import Mapped, mapped_column

from antang_api.database import Base


class UserRole(StrEnum):
    PATIENT = "patient"
    CLINICIAN = "clinician"
    RESEARCHER = "researcher"


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)

    username: Mapped[str] = mapped_column(String(32))

    username_normalized: Mapped[str] = mapped_column(String(32), unique=True)

    full_name: Mapped[str | None] = mapped_column(String(64))

    password_hash: Mapped[str] = mapped_column(String(255))

    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            values_callable=lambda roles: [role.value for role in roles],
            native_enum=False,
            create_constraint=True,
            name="user_role",
        ),
        default=UserRole.PATIENT,
        server_default="patient",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=true()
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LoginSession(Base):
    __tablename__ = "login_sessions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True)

    # Refresh 轮换形成一条单向链，确保旧 token 仍能退出刚创建的后继会话。
    replaced_by_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("login_sessions.id", ondelete="SET NULL"),
        unique=True,
    )

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
