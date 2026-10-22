from collections.abc import Awaitable, Callable, Iterator
from typing import cast

import numpy as np
import pytest
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import SecretStr, ValidationError
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from antang_api.knowledge import search as knowledge_search
from antang_api.knowledge.embeddings import KNOWLEDGE_EMBEDDING_DIM
from antang_api.models import KnowledgeChunk, KnowledgeDocument
from antang_api.settings import settings
from antang_api.tools.knowledge import (
    MAX_KNOWLEDGE_CHUNK_CHARS,
    MAX_KNOWLEDGE_TOOL_RESULT_CHARS,
    KnowledgeSearchRequest,
    _encoded_length,
    _fit_within_limit,
    build_knowledge_search_tool,
)


def unit_vector(position: int, weight: float = 1.0) -> list[float]:
    vector = np.zeros(KNOWLEDGE_EMBEDDING_DIM, dtype=np.float32)
    vector[position] = weight
    return [float(value) for value in vector]


def mixed_vector(first: float, second: float) -> list[float]:
    vector = np.zeros(KNOWLEDGE_EMBEDDING_DIM, dtype=np.float32)
    vector[0] = first
    vector[1] = second
    return [float(value) for value in vector]


async def add_document(
    session: AsyncSession,
    title: str,
    chunks: list[tuple[int, str, list[float]]],
    printed_pages: list[int | None] | None = None,
) -> None:
    document = KnowledgeDocument(
        folder="测试指南",
        title=title,
        page_count=max(page for page, _, _ in chunks),
        chunk_count=len(chunks),
        embedding_model="bge-m3",
        embedding_dim=KNOWLEDGE_EMBEDDING_DIM,
    )
    session.add(document)
    await session.flush()

    session.add_all(
        [
            KnowledgeChunk(
                document_id=document.id,
                page=page,
                printed_page=(
                    printed_pages[ordinal] if printed_pages is not None else None
                ),
                ordinal=ordinal,
                text=text,
                text_sha256=f"{ordinal:064d}",
                embedding=np.asarray(vector, dtype="<f4").tobytes(),
            )
            for ordinal, (page, text, vector) in enumerate(chunks)
        ]
    )
    await session.flush()


def session_factory_for(session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    assert session.bind is not None
    return async_sessionmaker(
        session.bind,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )


def tool_coroutine(tool: BaseTool) -> Callable[..., Awaitable[object]]:
    assert isinstance(tool, StructuredTool)
    assert tool.coroutine is not None
    return cast("Callable[..., Awaitable[object]]", tool.coroutine)


@pytest.fixture(autouse=True)
def clear_index_cache() -> Iterator[None]:
    """每个用例都从空缓存开始，避免进程内索引互相污染。"""

    knowledge_search.reset_knowledge_index()
    yield
    knowledge_search.reset_knowledge_index()


async def test_search_returns_the_most_similar_chunk_first(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await add_document(
        db_session,
        "低血糖处理指南",
        [(3, "出现低血糖先补充 15 克快速升糖碳水。", unit_vector(5))],
    )
    await add_document(
        db_session,
        "运动管理共识",
        [(7, "运动前应评估血糖并携带糖块。", mixed_vector(0.6, 0.8))],
    )

    async def fake_embed(text: str) -> list[float]:
        assert text == "夜里低血糖怎么办"
        return mixed_vector(0.6, 0.8)

    monkeypatch.setattr(knowledge_search, "embed_query", fake_embed)

    matches = await knowledge_search.search_knowledge(
        db_session,
        "夜里低血糖怎么办",
        top_k=5,
    )

    assert [match.title for match in matches] == ["运动管理共识"]
    assert matches[0].page == 7
    assert matches[0].score == pytest.approx(1.0, abs=1e-5)


async def test_search_drops_chunks_below_the_similarity_threshold(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await add_document(
        db_session,
        "与问题无关的指南",
        [(1, "这里讲的是别的内容。", unit_vector(1))],
    )

    async def fake_embed(text: str) -> list[float]:
        return unit_vector(0)

    monkeypatch.setattr(knowledge_search, "embed_query", fake_embed)

    matches = await knowledge_search.search_knowledge(db_session, "任意问题", top_k=5)

    assert matches == []


async def test_search_reports_an_empty_knowledge_base(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_embed(text: str) -> list[float]:
        raise AssertionError("知识库为空时不应调用向量化服务")

    monkeypatch.setattr(knowledge_search, "embed_query", fake_embed)

    assert await knowledge_search.search_knowledge(db_session, "任意问题", top_k=3) == []


async def test_search_rejects_a_vector_of_the_wrong_dimension(
    db_session: AsyncSession,
) -> None:
    await add_document(
        db_session,
        "长度错误的文档",
        [(1, "片段正文。", unit_vector(0))],
    )

    # 写入一段 512 维向量，模拟离线产物与配置不一致。
    await db_session.execute(
        update(KnowledgeChunk).values(
            embedding=np.zeros(512, dtype="<f4").tobytes()
        )
    )

    with pytest.raises(RuntimeError, match="向量长度与配置维度不一致"):
        await knowledge_search.search_knowledge(db_session, "任意问题", top_k=1)


async def test_tool_returns_title_page_and_truncated_text(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    long_text = "低血糖" * 400
    await add_document(
        db_session,
        "中国糖尿病防治指南（2024版）",
        [(12, long_text, unit_vector(0))],
    )

    async def fake_embed(text: str) -> list[float]:
        return unit_vector(0)

    monkeypatch.setattr(knowledge_search, "embed_query", fake_embed)

    tool = build_knowledge_search_tool(session_factory_for(db_session))
    payload = await tool_coroutine(tool)(KnowledgeSearchRequest(query="低血糖怎么处理"))

    assert isinstance(payload, dict)
    results = cast("list[dict[str, object]]", payload["results"])
    assert payload["query"] == "低血糖怎么处理"
    assert len(results) == 1
    assert results[0]["title"] == "中国糖尿病防治指南（2024版）"
    assert results[0]["page"] == 12
    text = cast("str", results[0]["text"])
    assert len(text) == MAX_KNOWLEDGE_CHUNK_CHARS + 1
    assert text.endswith("…")
    assert "note" not in payload


async def test_tool_explains_when_nothing_matches(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_embed(text: str) -> list[float]:
        return unit_vector(0)

    monkeypatch.setattr(knowledge_search, "embed_query", fake_embed)

    tool = build_knowledge_search_tool(session_factory_for(db_session))
    payload = await tool_coroutine(tool)(KnowledgeSearchRequest(query="无关的问题"))

    assert isinstance(payload, dict)
    assert payload["results"] == []
    assert "note" in payload


def test_request_rejects_unknown_arguments() -> None:
    with pytest.raises(ValidationError):
        KnowledgeSearchRequest.model_validate(
            {"query": "低血糖", "top_k": 3, "unexpected": True}
        )


def test_request_rejects_out_of_range_top_k() -> None:
    with pytest.raises(ValidationError):
        KnowledgeSearchRequest.model_validate({"query": "低血糖", "top_k": 99})


async def test_tool_cites_the_printed_page_of_a_journal_layout(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """期刊 PDF 第 19 页是印刷第 1161 页，引用必须给读者能翻到的那一页。"""

    await add_document(
        db_session,
        "中国1型糖尿病诊治指南（2021版）",
        [(19, "成人糖化血红蛋白控制目标为 7.0% 以下。", unit_vector(0))],
        printed_pages=[1161],
    )

    async def fake_embed(text: str) -> list[float]:
        return unit_vector(0)

    monkeypatch.setattr(knowledge_search, "embed_query", fake_embed)

    tool = build_knowledge_search_tool(session_factory_for(db_session))
    payload = await tool_coroutine(tool)(
        KnowledgeSearchRequest(query="成人糖化血红蛋白目标")
    )

    assert isinstance(payload, dict)
    results = cast("list[dict[str, object]]", payload["results"])
    assert results[0]["page"] == 1161
    assert results[0]["page_kind"] == "printed"
    assert results[0]["pdf_page"] == 19
    assert results[0]["cite"] == "（《中国1型糖尿病诊治指南（2021版）》第 1161 页）"


async def test_chinese_question_prefers_chinese_chunks(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """中文语料只占一成，中文提问时英文片段不能把中文指南挤出去。"""

    await add_document(
        db_session,
        "standards-of-care-2026",
        [
            (
                202,
                "GLP-1 receptor agonists are not indicated for type 1 diabetes.",
                mixed_vector(0.720, 0.694),
            )
        ],
    )
    await add_document(
        db_session,
        "中国糖尿病防治指南（2024版）",
        [
            (
                27,
                "司美格鲁肽目前未获批用于 1 型糖尿病。",
                mixed_vector(0.700, 0.714),
            )
        ],
    )

    async def fake_embed(text: str) -> list[float]:
        return unit_vector(0)

    monkeypatch.setattr(knowledge_search, "embed_query", fake_embed)

    matches = await knowledge_search.search_knowledge(
        db_session,
        "司美格鲁肽能用于1型糖尿病吗",
        top_k=2,
    )

    assert [match.title for match in matches] == ["中国糖尿病防治指南（2024版）", "standards-of-care-2026"]
    assert matches[1].score == pytest.approx(0.72, abs=1e-4)


def test_embedding_settings_fall_back_to_the_chat_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "knowledge_embedding_base_url", "")
    monkeypatch.setattr(settings, "knowledge_embedding_api_key", None)

    assert settings.knowledge_embedding_openai_base_url == settings.hachimi_openai_base_url
    assert (
        settings.resolved_knowledge_embedding_api_key
        == settings.hachimi_api_key.get_secret_value()
    )


def test_embedding_settings_can_use_a_separate_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "knowledge_embedding_base_url", "http://embeddings:9000/v1/")
    monkeypatch.setattr(settings, "knowledge_embedding_api_key", SecretStr("local-key"))

    assert settings.knowledge_embedding_openai_base_url == "http://embeddings:9000/v1"
    assert settings.resolved_knowledge_embedding_api_key == "local-key"


def test_oversized_results_are_trimmed_instead_of_failing() -> None:
    rendered = [
        {
            "title": "中国1型糖尿病诊治指南（2021版）",
            "page": index,
            "page_kind": "printed",
            "text": "血糖目标" * 100,
            "cite": f"（《中国1型糖尿病诊治指南（2021版）》第 {index} 页）",
        }
        for index in range(20)
    ]

    payload = _fit_within_limit("睡前血糖目标", rendered)

    kept = payload["results"]
    assert isinstance(kept, list)
    assert 0 < len(kept) < len(rendered)
    assert "未展示" in str(payload["note"])
    assert _encoded_length(payload) <= MAX_KNOWLEDGE_TOOL_RESULT_CHARS
