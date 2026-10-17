"""create psychosocial assessments

Revision ID: l59c4e8b2d71
Revises: k48f9e2a6b73
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "l59c4e8b2d71"
down_revision: str | None = "k48f9e2a6b73"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "psychosocial_assessments",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("uuidv7()"),
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("hfs_behavior_percent", sa.Integer(), nullable=False),
        sa.Column("hfs_worry_percent", sa.Integer(), nullable=False),
        sa.Column("gold_score", sa.Integer(), nullable=True),
        sa.Column("instrument", sa.String(length=64), nullable=False),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "hfs_behavior_percent BETWEEN 0 AND 100",
            name="ck_psychosocial_hfs_behavior",
        ),
        sa.CheckConstraint(
            "hfs_worry_percent BETWEEN 0 AND 100",
            name="ck_psychosocial_hfs_worry",
        ),
        sa.CheckConstraint(
            "gold_score IS NULL OR (gold_score BETWEEN 1 AND 7)",
            name="ck_psychosocial_gold_score",
        ),
    )
    op.create_index(
        "ix_psychosocial_assessments_user_id",
        "psychosocial_assessments",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_psychosocial_assessments_user_id",
        table_name="psychosocial_assessments",
    )
    op.drop_table("psychosocial_assessments")
