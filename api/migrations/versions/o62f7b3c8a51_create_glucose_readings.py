"""glucose readings

Revision ID: o62f7b3c8a51
Revises: n61e6a4f9d82
Create Date: 2026-10-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "o62f7b3c8a51"
down_revision: str | None = "n61e6a4f9d82"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONTEXTS_SQL = ", ".join(
    f"'{value}'"
    for value in ("fasting", "pre_meal", "post_meal", "bedtime", "night", "other")
)
_SOURCES_SQL = ", ".join(f"'{value}'" for value in ("manual", "report"))


def upgrade() -> None:
    op.create_table(
        "glucose_readings",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("value_mg_dl", sa.Integer(), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "context",
            sa.String(length=32),
            server_default=sa.text("'other'"),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.String(length=16),
            server_default=sa.text("'manual'"),
            nullable=False,
        ),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "value_mg_dl BETWEEN 20 AND 600", name="ck_glucose_value_range"
        ),
        sa.CheckConstraint(f"context IN ({_CONTEXTS_SQL})", name="ck_glucose_context"),
        sa.CheckConstraint(f"source IN ({_SOURCES_SQL})", name="ck_glucose_source"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_glucose_readings_user_id", "glucose_readings", ["user_id"])
    op.create_index(
        "ix_glucose_readings_measured_at", "glucose_readings", ["measured_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_glucose_readings_measured_at", table_name="glucose_readings")
    op.drop_index("ix_glucose_readings_user_id", table_name="glucose_readings")
    op.drop_table("glucose_readings")
