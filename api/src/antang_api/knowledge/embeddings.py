"""把检索问题编码成向量，走项目已有的 OpenAI 兼容中转站。"""

from openai import AsyncOpenAI, OpenAIError

from antang_api.settings import settings

KNOWLEDGE_EMBEDDING_MODEL = "bge-m3"
KNOWLEDGE_EMBEDDING_DIM = 1024
_EMBEDDING_TIMEOUT_SECONDS = 30.0


class KnowledgeEmbeddingError(RuntimeError):
    """检索问题的向量化失败。"""


_client: AsyncOpenAI | None = None


def _shared_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.hachimi_api_key.get_secret_value(),
            base_url=settings.hachimi_openai_base_url,
            timeout=_EMBEDDING_TIMEOUT_SECONDS,
            max_retries=2,
        )
    return _client


async def embed_query(text: str) -> list[float]:
    """返回问题的定长向量；维度不符或请求失败都直接报错。"""

    stripped = text.strip()
    if not stripped:
        raise KnowledgeEmbeddingError("检索问题不能为空")

    try:
        response = await _shared_client().embeddings.create(
            model=KNOWLEDGE_EMBEDDING_MODEL,
            input=stripped,
        )
    except OpenAIError as error:
        raise KnowledgeEmbeddingError(
            f"知识库检索问题向量化失败：{type(error).__name__}"
        ) from error

    if not response.data:
        raise KnowledgeEmbeddingError("向量化服务没有返回结果")

    vector = [float(value) for value in response.data[0].embedding]
    if len(vector) != KNOWLEDGE_EMBEDDING_DIM:
        raise KnowledgeEmbeddingError(
            f"向量维度应为 {KNOWLEDGE_EMBEDDING_DIM}，实际为 {len(vector)}"
        )
    return vector
