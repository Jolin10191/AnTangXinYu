"""Add shared clinical read scope; preserve all existing roles and grants."""
from alembic import op
import sqlalchemy as sa

revision = "s86dbf802a15"
down_revision = "r75cae7f1d94"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "clinical_access_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("id = 1", name="ck_clinical_settings_singleton"),
    )
    op.create_table(
        "clinical_access_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("login_session_id", sa.Uuid(), sa.ForeignKey("login_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("password_revision", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_clinical_access_sessions_user_id", "clinical_access_sessions", ["user_id"])


def downgrade() -> None:
    op.drop_table("clinical_access_sessions")
    op.drop_table("clinical_access_settings")

