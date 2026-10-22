"""add printed page to knowledge chunks

Revision ID: k48f9e2a6b73
Revises: j37e8d1f5a62
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "k48f9e2a6b73"
down_revision: str | None = "j37e8d1f5a62"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_chunks",
        sa.Column("printed_page", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_chunks", "printed_page")
