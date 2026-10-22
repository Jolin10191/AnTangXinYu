"""create knowledge base

Revision ID: j37e8d1f5a62
Revises: i26c7d9e4f30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "j37e8d1f5a62"
down_revision: str | None = "i26c7d9e4f30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("folder", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("embedding_model", sa.String(length=64), nullable=False),
        sa.Column("embedding_dim", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "page_count > 0",
            name="ck_knowledge_documents_page_count",
        ),
        sa.CheckConstraint(
            "chunk_count > 0",
            name="ck_knowledge_documents_chunk_count",
        ),
        sa.CheckConstraint(
            "embedding_dim > 0",
            name="ck_knowledge_documents_embedding_dim",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "folder",
            "title",
            name="uq_knowledge_documents_folder_title",
        ),
    )
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_sha256", sa.String(length=64), nullable=False),
        sa.Column("embedding", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("page > 0", name="ck_knowledge_chunks_page"),
        sa.CheckConstraint("ordinal >= 0", name="ck_knowledge_chunks_ordinal"),
        sa.CheckConstraint(
            "length(embedding) > 0",
            name="ck_knowledge_chunks_embedding",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["knowledge_documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "page",
            "ordinal",
            name="uq_knowledge_chunks_document_page_ordinal",
        ),
    )
    op.create_index(
        "ix_knowledge_chunks_document_id",
        "knowledge_chunks",
        ["document_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_knowledge_chunks_document_id",
        table_name="knowledge_chunks",
    )
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
