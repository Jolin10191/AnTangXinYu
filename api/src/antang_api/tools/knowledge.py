"""糖尿病知识库检索工具：从指南与共识原文里找依据。"""

import json
from typing import Annotated

from langchain.tools import tool
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from antang_api.database import session_factory as default_session_factory
from antang_api.knowledge import KnowledgeMatch, search_knowledge

MAX_KNOWLEDGE_TOOL_RESULT_CHARS = 6_000
MAX_KNOWLEDGE_CHUNK_CHARS = 700
# 给「还有几条没展示」这句说明留出空间，免得裁剪后反而超出上限。
RESULT_NOTE_RESERVE_CHARS = 200


def _encoded_length(payload: dict[str, object]) -> int:
    return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def _fit_within_limit(query: str, rendered: list[dict[str, object]]) -> dict[str, object]:
    """按相关度顺序保留能放进上限的片段，并说明还有几条被省略。

    上限是固定的，超了就丢掉排后面的片段而不是让整轮对话失败：检索工具
    返回几条都能用，失败一次却会让用户拿不到任何回答。
    """

    kept: list[dict[str, object]] = []
    for item in rendered:
        trial = {"query": query, "results": [*kept, item]}
        if _encoded_length(trial) > MAX_KNOWLEDGE_TOOL_RESULT_CHARS - RESULT_NOTE_RESERVE_CHARS:
            break
        kept.append(item)

    payload: dict[str, object] = {"query": query, "results": kept}
    dropped = len(rendered) - len(kept)
    if not kept:
        payload["note"] = "知识库没有返回能在长度上限内展示的片段，请换一个更具体的问题。"
    elif dropped:
        payload["note"] = f"只展示相关度最高的 {len(kept)} 条，另有 {dropped} 条因长度上限未展示。"
    return payload


class KnowledgeSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: Annotated[
        str,
        Field(
            min_length=2,
            max_length=120,
            description=(
                "要检索的医学问题，用中文写清主题即可，"
                "例如“夜间低血糖的预防”。"
            ),
        ),
    ]
    top_k: Annotated[
        int,
        Field(ge=1, le=8, description="返回的片段数量，默认 5。"),
    ] = 5


def _render_match(match: KnowledgeMatch) -> dict[str, object]:
    text = match.text.strip()
    if len(text) > MAX_KNOWLEDGE_CHUNK_CHARS:
        text = text[:MAX_KNOWLEDGE_CHUNK_CHARS].rstrip() + "…"
    # 期刊排版的文件里 PDF 页和印刷页不同，读者只能按印刷页翻，所以优先给
    # printed_page；没有印刷页码时才退回 PDF 页并说明是哪一种。
    cite_page = match.printed_page if match.printed_page is not None else match.page
    return {
        "title": match.title,
        # 现成的出处串，模型整段复制比自己拼写更不容易写错页码。
        "cite": f"（《{match.title}》第 {cite_page} 页）",
        "page": cite_page,
        "page_kind": "printed" if match.printed_page is not None else "pdf",
        "pdf_page": match.page,
        "text": text,
        "score": round(match.score, 4),
    }


def build_knowledge_search_tool(
    session_factory: async_sessionmaker[AsyncSession] = default_session_factory,
) -> BaseTool:
    """创建检索项目内糖尿病知识库的共享工具。"""

    @tool("search_diabetes_knowledge")
    async def search_diabetes_knowledge(
        request: KnowledgeSearchRequest,
    ) -> dict[str, object]:
        """在糖尿病指南与专家共识的知识库里检索原文片段。

        用户询问糖尿病的医学常识、指南推荐、指标范围（例如血糖、糖化
        血红蛋白、血压血脂的目标值）、低血糖的处理与预防、饮食与运动原则、
        胰岛素与器械使用时，先用它找依据，不要凭记忆给出指南编号或数值。
        每条结果都带有来源标题和页码：page_kind 为 printed 时 page 是期刊上
        印的页码，为 pdf 时 page 是文件页码，两种情况都直接引用 page 这个数。
        回答时把出处写成“《标题》第 N 页”。
        它不能查用户自己的手环数据（那要用设备数据读取工具），也不用于
        闲聊、时事或需要联网的最新信息。
        """

        async with session_factory() as session:
            matches = await search_knowledge(
                session,
                request.query,
                top_k=request.top_k,
            )

        payload = _fit_within_limit(
            request.query,
            [_render_match(match) for match in matches],
        )
        if not matches:
            payload["note"] = "知识库没有检索到足够相关的片段。"
        return payload

    return search_diabetes_knowledge
