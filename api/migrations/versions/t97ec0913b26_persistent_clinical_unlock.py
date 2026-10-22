"""Remove the secondary unlock time limit; personal authentication remains required."""
from alembic import op
import sqlalchemy as sa

revision = "t97ec0913b26"
down_revision = "s86dbf802a15"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("clinical_access_sessions", "expires_at", existing_type=sa.DateTime(timezone=True), nullable=True)
    op.execute("UPDATE clinical_access_sessions SET expires_at = NULL")


def downgrade() -> None:
    # Rollback invalidates unlimited secondary sessions rather than assigning a fake expiry.
    op.execute("DELETE FROM clinical_access_sessions WHERE expires_at IS NULL")
    op.alter_column("clinical_access_sessions", "expires_at", existing_type=sa.DateTime(timezone=True), nullable=False)
