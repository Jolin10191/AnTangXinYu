"""把离线产出的知识库片段灌入数据库。

在 api 容器内运行：

    python /app/scripts/load_knowledge.py --path /tmp/knowledge_chunks.jsonl

脚本是幂等的：每次先清空知识库两张表，再按文档顺序写入，
所以重复执行不会产生重复片段。
"""

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy import delete, insert
from sqlalchemy.ext.asyncio import AsyncSession

from antang_api.database import engine, session_factory
from antang_api.knowledge.embeddings import (
    KNOWLEDGE_EMBEDDING_DIM,
    embedding_model,
)
from antang_api.models import KnowledgeChunk, KnowledgeDocument

_BATCH_ROWS = 400


def _normalized(embedding: list[float]) -> bytes:
    vector = np.asarray(embedding, dtype=np.float32)
    if vector.shape != (KNOWLEDGE_EMBEDDING_DIM,):
        raise ValueError(f"向量维度应为 {KNOWLEDGE_EMBEDDING_DIM}，实际为 {vector.shape}")
    norm = float(np.linalg.norm(vector))
    if norm == 0:
        raise ValueError("知识库片段向量为零向量")
    return (vector / norm).astype("<f4").tobytes()


async def _flush(
    session: AsyncSession,
    key: tuple[str, str],
    buffer: list[dict[str, Any]],
) -> None:
    folder, title = key
    document = KnowledgeDocument(
        folder=folder,
        title=title,
        page_count=max(int(record["page"]) for record in buffer),
        chunk_count=len(buffer),
        embedding_model=embedding_model(),
        embedding_dim=KNOWLEDGE_EMBEDDING_DIM,
    )
    session.add(document)
    await session.flush()

    rows = [
        {
            "document_id": document.id,
            "page": int(record["page"]),
            "printed_page": (
                int(record["printed_page"]) if record.get("printed_page") is not None else None
            ),
            "ordinal": int(record["ordinal"]),
            "text": record["text"],
            "text_sha256": record["sha256"],
            "embedding": _normalized(record["embedding"]),
        }
        for record in buffer
    ]
    for start in range(0, len(rows), _BATCH_ROWS):
        await session.execute(insert(KnowledgeChunk), rows[start : start + _BATCH_ROWS])


async def load(path: Path) -> tuple[int, int]:
    """按文档顺序写入全部片段，返回（文档数, 片段数）。"""

    documents = 0
    chunks = 0
    current_key: tuple[str, str] | None = None
    buffer: list[dict[str, Any]] = []
    started = time.monotonic()

    async with session_factory() as session:
        await session.execute(delete(KnowledgeDocument))

        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = json.loads(line)
                key = (str(record["folder"]), str(record["title"]))
                if key != current_key:
                    if buffer and current_key is not None:
                        await _flush(session, current_key, buffer)
                        documents += 1
                        chunks += len(buffer)
                        print(
                            f"[{documents}] {current_key[1]} chunks={len(buffer)} "
                            f"elapsed={time.monotonic() - started:.0f}s",
                            flush=True,
                        )
                    current_key = key
                    buffer = []
                buffer.append(record)

        if buffer and current_key is not None:
            await _flush(session, current_key, buffer)
            documents += 1
            chunks += len(buffer)

        await session.commit()

    return documents, chunks


async def main() -> None:
    parser = argparse.ArgumentParser(description="把知识库片段灌入数据库")
    parser.add_argument("--path", required=True, type=Path, help="knowledge_chunks.jsonl")
    arguments = parser.parse_args()

    if not arguments.path.is_file():
        raise SystemExit(f"找不到片段文件：{arguments.path}")

    try:
        documents, chunks = await load(arguments.path)
        print(f"done: documents={documents} chunks={chunks}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
