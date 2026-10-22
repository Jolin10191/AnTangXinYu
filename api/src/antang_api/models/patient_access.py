"""患者授权历史与最小访问审计；不保存健康正文。"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from antang_api.database import Base


class PatientAccessGrant(Base):
    __tablename__ = "patient_access_grants"
    __table_args__ = (
        Index(
            "uq_active_patient_clinician",
            "patient_id",
            "clinician_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index("ix_grants_clinician_patient", "clinician_id", "patient_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    clinician_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PatientAccessAudit(Base):
    __tablename__ = "patient_access_audits"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    maintainer: Mapped[str | None] = mapped_column(String(128))
    patient_id: Mapped[UUID | None] = mapped_column(Uuid)
    target_user_id: Mapped[UUID | None] = mapped_column(Uuid)
    grant_id: Mapped[UUID | None] = mapped_column(Uuid)
    action: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
