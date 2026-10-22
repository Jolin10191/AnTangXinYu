"""Merge reviewed clinician access with the deployed health feature branch.

Both parent chains were already used independently. Keep their revision IDs so
existing local and production databases can apply only their missing branch.
"""

revision = "r75cae7f1d94"
down_revision = ("k48e9f1a6b52", "q64b9d6e0c83")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
