"""speech cues heard from a voice message

Revision ID: q64b9d6e0c83
Revises: p63a8c5d9b72
Create Date: 2026-10-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "q64b9d6e0c83"
down_revision: str | None = "p63a8c5d9b72"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PACES_SQL = "'slow', 'normal', 'fast', 'unknown'"
_ENERGIES_SQL = "'low', 'normal', 'high', 'unknown'"
_BREATHING_SQL = "'audible', 'none', 'unknown'"


def upgrade() -> None:
    op.create_table(
        "speech_cues",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "pace",
            sa.String(length=16),
            server_default=sa.text("'unknown'"),
            nullable=False,
        ),
        sa.Column(
            "energy",
            sa.String(length=16),
            server_default=sa.text("'unknown'"),
            nullable=False,
        ),
        sa.Column(
            "breathing",
            sa.String(length=16),
            server_default=sa.text("'unknown'"),
            nullable=False,
        ),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("model_name", sa.String(length=64), nullable=False),
        sa.Column("heard_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(f"pace IN ({_PACES_SQL})", name="ck_speech_cue_pace"),
        sa.CheckConstraint(
            f"energy IN ({_ENERGIES_SQL})", name="ck_speech_cue_energy"
        ),
        sa.CheckConstraint(
            f"breathing IN ({_BREATHING_SQL})", name="ck_speech_cue_breathing"
        ),
        sa.CheckConstraint(
            "confidence BETWEEN 0 AND 1",
            name="ck_speech_cue_confidence",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_speech_cues_user_id", "speech_cues", ["user_id"])
    op.create_index("ix_speech_cues_heard_at", "speech_cues", ["heard_at"])


def downgrade() -> None:
    op.drop_index("ix_speech_cues_heard_at", table_name="speech_cues")
    op.drop_index("ix_speech_cues_user_id", table_name="speech_cues")
    op.drop_table("speech_cues")
