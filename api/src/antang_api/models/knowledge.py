from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from antang_api.database import Base


class KnowledgeDocument(Base):
    """知识库的一份来源文件，例如一份指南或共识。"""

    __tablename__ = "knowledge_documents"
    __table_args__ = (
        UniqueConstraint(
            "folder",
            "title",
            name="uq_knowledge_documents_folder_title",
        ),
        CheckConstraint("page_count > 0", name="ck_knowledge_documents_page_count"),
        CheckConstraint("chunk_count > 0", name="ck_knowledge_documents_chunk_count"),
        CheckConstraint(
            "embedding_dim > 0",
            name="ck_knowledge_documents_embedding_dim",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("uuidv7()")
    )
    folder: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(300))
    page_count: Mapped[int] = mapped_column(Integer)
    chunk_count: Mapped[int] = mapped_column(Integer)
    embedding_model: Mapped[str] = mapped_column(String(64))
    embedding_dim: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class KnowledgeChunk(Base):
    """知识库的一个原文片段，向量已按行做过 L2 归一化。"""

    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "page",
            "ordinal",
            name="uq_knowledge_chunks_document_page_ordinal",
        ),
        CheckConstraint("page > 0", name="ck_knowledge_chunks_page"),
        CheckConstraint("ordinal >= 0", name="ck_knowledge_chunks_ordinal"),
        CheckConstraint("length(embedding) > 0", name="ck_knowledge_chunks_embedding"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("uuidv7()")
    )
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True
    )
    page: Mapped[int] = mapped_column(Integer)
    ordinal: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    text_sha256: Mapped[str] = mapped_column(String(64))
    # float32 小端、定长 embedding_dim * 4 字节，不含分隔符。
    embedding: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
