"""fear behaviors and hypoglycemia belief events

Revision ID: n61e6a4f9d82
Revises: m60d5f9c3e84
Create Date: 2026-10-20

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "n61e6a4f9d82"
down_revision: str | None = "m60d5f9c3e84"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BEHAVIOR_KINDS = (
    "'extra_check'",
    "'night_check'",
    "'comfort_meal'",
    "'exercise_avoidance'",
    "'insulin_hold'",
)
_BEHAVIOR_KINDS_SQL = ", ".join(_BEHAVIOR_KINDS)

_BELIEF_CODES_SQL = ", ".join(
    f"'{code}'"
    for code in (
        "hypo_causes_death",
        "hypo_causes_coma",
        "hypo_is_losing_control",
        "hypo_reveals_weakness",
        "hypo_is_my_fault",
        "hypo_always_repeats",
        "hypo_cannot_be_detected",
        "hypo_blocks_normal_life",
    )
)

_BELIEF_OCCURRENCES_SQL = "'mentioned', 'reframed', 'denied'"


def upgrade() -> None:
    op.create_table(
        "fear_behavior_logs",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("source_message_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"kind IN ({_BEHAVIOR_KINDS_SQL})",
            name="ck_fear_behavior_kind",
        ),
        sa.CheckConstraint(
            "count BETWEEN 1 AND 50",
            name="ck_fear_behavior_count",
        ),
        sa.ForeignKeyConstraint(
            ["source_message_id"],
            ["messages.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fear_behavior_logs_user_id",
        "fear_behavior_logs",
        ["user_id"],
    )
    op.create_index(
        "ix_fear_behavior_logs_occurred_at",
        "fear_behavior_logs",
        ["occurred_at"],
    )

    op.create_table(
        "hypoglycemia_belief_events",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("belief_code", sa.String(length=48), nullable=False),
        sa.Column("quote", sa.String(length=300), nullable=False),
        sa.Column("trigger_context", sa.String(length=200), nullable=True),
        sa.Column("fear_intensity", sa.Integer(), nullable=True),
        sa.Column("occurrence", sa.String(length=16), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_message_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"belief_code IN ({_BELIEF_CODES_SQL})",
            name="ck_belief_code",
        ),
        sa.CheckConstraint(
            f"occurrence IN ({_BELIEF_OCCURRENCES_SQL})",
            name="ck_belief_occurrence",
        ),
        sa.CheckConstraint(
            "fear_intensity IS NULL OR (fear_intensity BETWEEN 0 AND 100)",
            name="ck_belief_fear_intensity",
        ),
        sa.ForeignKeyConstraint(
            ["source_message_id"],
            ["messages.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_hypoglycemia_belief_events_user_id",
        "hypoglycemia_belief_events",
        ["user_id"],
    )
    op.create_index(
        "ix_hypoglycemia_belief_events_belief_code",
        "hypoglycemia_belief_events",
        ["belief_code"],
    )
    op.create_index(
        "ix_hypoglycemia_belief_events_detected_at",
        "hypoglycemia_belief_events",
        ["detected_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_hypoglycemia_belief_events_detected_at",
        table_name="hypoglycemia_belief_events",
    )
    op.drop_index(
        "ix_hypoglycemia_belief_events_belief_code",
        table_name="hypoglycemia_belief_events",
    )
    op.drop_index(
        "ix_hypoglycemia_belief_events_user_id",
        table_name="hypoglycemia_belief_events",
    )
    op.drop_table("hypoglycemia_belief_events")
    op.drop_index(
        "ix_fear_behavior_logs_occurred_at",
        table_name="fear_behavior_logs",
    )
    op.drop_index(
        "ix_fear_behavior_logs_user_id",
        table_name="fear_behavior_logs",
    )
    op.drop_table("fear_behavior_logs")
