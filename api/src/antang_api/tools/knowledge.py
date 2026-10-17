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


class KnowledgeToolResultTooLargeError(RuntimeError):
    """知识库检索结果超过固定上限；正常参数下不会触发。"""


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
    return {
        "title": match.title,
        "page": match.page,
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
        每条结果都带有来源标题和页码，回答时把出处写成“《标题》第 N 页”。
        它不能查用户自己的手环数据（那要用设备数据读取工具），也不用于
        闲聊、时事或需要联网的最新信息。
        """

        async with session_factory() as session:
            matches = await search_knowledge(
                session,
                request.query,
                top_k=request.top_k,
            )

        payload: dict[str, object] = {
            "query": request.query,
            "results": [_render_match(match) for match in matches],
        }
        if not matches:
            payload["note"] = "知识库没有检索到足够相关的片段。"

        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        if len(encoded) > MAX_KNOWLEDGE_TOOL_RESULT_CHARS:
            raise KnowledgeToolResultTooLargeError(
                "知识库检索结果超过固定上限，请缩小问题范围或减少片段数量"
            )
        return payload

    return search_diabetes_knowledge
