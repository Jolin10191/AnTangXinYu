"""知识库检索：在进程内做精确余弦检索。

知识库规模是几千个片段，精确检索的召回率高于任何近似索引，
单次查询也只有毫秒级开销；索引在首次使用时整表载入内存，
按行数与最后写入时间判断是否需要重建。
"""

import asyncio
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from antang_api.knowledge.embeddings import (
    KNOWLEDGE_EMBEDDING_DIM,
    embed_query,
)
from antang_api.models import KnowledgeChunk, KnowledgeDocument

# 低于该余弦相似度的片段与问题无关，不交给模型，避免它把无关条文当依据。
MIN_KNOWLEDGE_SCORE = 0.32


@dataclass(frozen=True)
class KnowledgeMatch:
    """一条命中的原文片段及其出处。"""

    title: str
    page: int
    text: str
    score: float


@dataclass(frozen=True)
class _Index:
    fingerprint: tuple[int, object]
    titles: tuple[str, ...]
    pages: tuple[int, ...]
    texts: tuple[str, ...]
    matrix: NDArray[np.float32]


_index: _Index | None = None
_index_lock = asyncio.Lock()


async def _current_fingerprint(session: AsyncSession) -> tuple[int, object]:
    count, latest = (
        await session.execute(
            select(func.count(KnowledgeChunk.id), func.max(KnowledgeChunk.created_at))
        )
    ).one()
    return int(count or 0), latest


async def _build_index(
    session: AsyncSession,
    fingerprint: tuple[int, object],
) -> _Index:
    rows = (
        await session.execute(
            select(
                KnowledgeDocument.title,
                KnowledgeChunk.page,
                KnowledgeChunk.text,
                KnowledgeChunk.embedding,
            )
            .join(KnowledgeChunk, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .order_by(KnowledgeChunk.id)
        )
    ).all()

    if not rows:
        return _Index(
            fingerprint=fingerprint,
            titles=(),
            pages=(),
            texts=(),
            matrix=np.zeros((0, KNOWLEDGE_EMBEDDING_DIM), dtype=np.float32),
        )

    width = KNOWLEDGE_EMBEDDING_DIM * 4
    for row in rows:
        if len(row.embedding) != width:
            raise RuntimeError(
                "知识库片段向量长度与配置维度不一致，"
                f"期望 {width} 字节，实际 {len(row.embedding)} 字节"
            )

    matrix = np.frombuffer(  # pyright: ignore[reportArgumentType]
        b"".join(row.embedding for row in rows),
        dtype="<f4",
    ).reshape(len(rows), KNOWLEDGE_EMBEDDING_DIM)
    norms = np.linalg.norm(matrix, axis=1)
    if np.any(norms == 0):
        raise RuntimeError("知识库存在零向量片段，无法做余弦检索")

    return _Index(
        fingerprint=fingerprint,
        titles=tuple(row.title for row in rows),
        pages=tuple(int(row.page) for row in rows),
        texts=tuple(row.text for row in rows),
        matrix=(matrix / norms[:, None]).astype(np.float32),
    )


async def _get_index(session: AsyncSession) -> _Index:
    global _index

    fingerprint = await _current_fingerprint(session)
    if _index is not None and _index.fingerprint == fingerprint:
        return _index

    async with _index_lock:
        if _index is not None and _index.fingerprint == fingerprint:
            return _index
        _index = await _build_index(session, fingerprint)
        return _index


async def warm_knowledge_index(session: AsyncSession) -> None:
    """启动时预载索引，避免第一位用户等待建索引。"""

    await _get_index(session)


def reset_knowledge_index() -> None:
    """清空进程内缓存；写库或测试之间切换数据集时使用。"""

    global _index
    _index = None


async def search_knowledge(
    session: AsyncSession,
    query: str,
    *,
    top_k: int,
) -> list[KnowledgeMatch]:
    """返回与问题最相关的片段，按相似度从高到低排列。"""

    index = await _get_index(session)
    if not index.titles:
        return []

    vector = np.asarray(await embed_query(query), dtype=np.float32)
    norm = float(np.linalg.norm(vector))
    if norm == 0:
        raise RuntimeError("检索问题的向量为零向量")
    scores = index.matrix @ (vector / norm)

    limit = min(top_k, len(scores))
    if limit < len(scores):
        candidates = np.argpartition(-scores, limit - 1)[:limit]
    else:
        candidates = np.arange(len(scores))
    ordered = candidates[np.argsort(-scores[candidates])]

    matches: list[KnowledgeMatch] = []
    for position in ordered:
        score = float(scores[position])
        if score < MIN_KNOWLEDGE_SCORE:
            continue
        matches.append(
            KnowledgeMatch(
                title=index.titles[position],
                page=index.pages[position],
                text=index.texts[position],
                score=score,
            )
        )
    return matches
