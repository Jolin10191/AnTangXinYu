"""Account names and reviewed clinician applications.

Revision ID: k48e9f1a6b52
Revises: j37d8e0f5a41
"""

from alembic import op
import sqlalchemy as sa

revision = "k48e9f1a6b52"
down_revision = "j37d8e0f5a41"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("full_name", sa.String(64)))
    op.create_table(
        "clinician_applications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("full_name", sa.String(64), nullable=False),
        sa.Column("organization", sa.String(128), nullable=False),
        sa.Column("status", sa.String(8), nullable=False, server_default="pending"),
        sa.Column(
            "reviewed_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("rejection_reason", sa.String(512)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="clinician_application_status",
        ),
    )
    op.create_index(
        "ix_clinician_applications_user_id", "clinician_applications", ["user_id"]
    )
    op.create_index(
        "ix_clinician_application_status_id", "clinician_applications", ["status", "id"]
    )
    op.create_index(
        "uq_pending_clinician_application",
        "clinician_applications",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_table("clinician_applications")
    op.drop_column("users", "full_name")
