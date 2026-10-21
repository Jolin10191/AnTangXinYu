"""Add a reviewed_at column for the 24 hour hypo review.

Revision ID: p63a8c5d9b72
Revises: o62f7b3c8a51
Create Date: 2026-10-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "p63a8c5d9b72"
down_revision: str | None = "o62f7b3c8a51"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "glucose_readings",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("glucose_readings", "reviewed_at")
