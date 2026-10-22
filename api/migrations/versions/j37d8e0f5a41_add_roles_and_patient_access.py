"""Add roles, patient grants and access audit.

Revision ID: j37d8e0f5a41
Revises: i26c7d9e4f30
"""

from alembic import op
import sqlalchemy as sa

revision = "j37d8e0f5a41"
down_revision = "i26c7d9e4f30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(10), nullable=False, server_default="patient"),
    )
    op.create_check_constraint(
        "user_role", "users", "role IN ('patient', 'clinician', 'researcher')"
    )
    op.create_table(
        "patient_access_grants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "patient_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "clinician_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "uq_active_patient_clinician",
        "patient_access_grants",
        ["patient_id", "clinician_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(
        "ix_grants_clinician_patient",
        "patient_access_grants",
        ["clinician_id", "patient_id"],
    )
    op.create_table(
        "patient_access_audits",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "actor_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("maintainer", sa.String(128)),
        sa.Column("patient_id", sa.Uuid()),
        sa.Column("target_user_id", sa.Uuid()),
        sa.Column("grant_id", sa.Uuid()),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("patient_access_audits")
    op.drop_table("patient_access_grants")
    op.drop_constraint("user_role", "users", type_="check")
    op.drop_column("users", "role")
