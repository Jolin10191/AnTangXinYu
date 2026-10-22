"""医护申请历史；待审批身份不提供医护数据访问权。"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from antang_api.database import Base


class ApplicationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ClinicianApplication(Base):
    __tablename__ = "clinician_applications"
    __table_args__ = (
        Index(
            "uq_pending_clinician_application",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        Index("ix_clinician_application_status_id", "status", "id"),
    )

    # 有序 ID 让同一事务时间内的重新申请也能确定先后。
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=func.uuidv7())
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    full_name: Mapped[str] = mapped_column(String(64))
    organization: Mapped[str] = mapped_column(String(128))
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(
            ApplicationStatus,
            values_callable=lambda values: [v.value for v in values],
            native_enum=False,
            create_constraint=True,
            name="clinician_application_status",
        ),
        default=ApplicationStatus.PENDING,
        server_default="pending",
    )
    reviewed_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
