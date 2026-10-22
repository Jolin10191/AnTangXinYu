"""rename fear score columns

Revision ID: m60d5f9c3e84
Revises: l59c4e8b2d71
"""

from collections.abc import Sequence

from alembic import op

revision: str = "m60d5f9c3e84"
down_revision: str | None = "l59c4e8b2d71"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "psychosocial_assessments"


def upgrade() -> None:
    op.drop_constraint("ck_psychosocial_hfs_behavior", TABLE, type_="check")
    op.drop_constraint("ck_psychosocial_hfs_worry", TABLE, type_="check")
    op.alter_column(
        TABLE,
        "hfs_behavior_percent",
        new_column_name="fear_behavior_percent",
    )
    op.alter_column(
        TABLE,
        "hfs_worry_percent",
        new_column_name="fear_worry_percent",
    )
    op.create_check_constraint(
        "ck_psychosocial_fear_behavior",
        TABLE,
        "fear_behavior_percent BETWEEN 0 AND 100",
    )
    op.create_check_constraint(
        "ck_psychosocial_fear_worry",
        TABLE,
        "fear_worry_percent BETWEEN 0 AND 100",
    )


def downgrade() -> None:
    op.drop_constraint("ck_psychosocial_fear_behavior", TABLE, type_="check")
    op.drop_constraint("ck_psychosocial_fear_worry", TABLE, type_="check")
    op.alter_column(
        TABLE,
        "fear_behavior_percent",
        new_column_name="hfs_behavior_percent",
    )
    op.alter_column(
        TABLE,
        "fear_worry_percent",
        new_column_name="hfs_worry_percent",
    )
    op.create_check_constraint(
        "ck_psychosocial_hfs_behavior",
        TABLE,
        "hfs_behavior_percent BETWEEN 0 AND 100",
    )
    op.create_check_constraint(
        "ck_psychosocial_hfs_worry",
        TABLE,
        "hfs_worry_percent BETWEEN 0 AND 100",
    )
