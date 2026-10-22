"""把检索问题编码成向量。

向量化与对话共用同一个中转站时，任一处欠费会让两边一起停。
这里优先读 KNOWLEDGE_EMBEDDING_* 三个配置项，留空才回退到 HACHIMI_*。
"""

from openai import AsyncOpenAI, OpenAIError

from antang_api.settings import settings

KNOWLEDGE_EMBEDDING_DIM = 1024
_EMBEDDING_TIMEOUT_SECONDS = 30.0


class KnowledgeEmbeddingError(RuntimeError):
    """检索问题的向量化失败。"""


def embedding_model() -> str:
    """向量化模型名；换模型必须同时重建索引。"""

    return settings.knowledge_embedding_model


_client: AsyncOpenAI | None = None
_client_signature: tuple[str, str] | None = None


def _shared_client() -> AsyncOpenAI:
    """按（地址, 钥匙）缓存客户端，配置变了会自动换一个。"""

    global _client, _client_signature
    base_url = settings.knowledge_embedding_openai_base_url
    api_key = settings.resolved_knowledge_embedding_api_key
    signature = (base_url, api_key[-4:])
    if _client is None or _client_signature != signature:
        _client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=_EMBEDDING_TIMEOUT_SECONDS,
            max_retries=2,
        )
        _client_signature = signature
    return _client


def reset_embedding_client() -> None:
    """丢掉缓存的客户端，测试与热切换配置时使用。"""

    global _client, _client_signature
    _client = None
    _client_signature = None


async def embed_query(text: str) -> list[float]:
    """返回问题的定长向量；维度不符或请求失败都直接报错。"""

    stripped = text.strip()
    if not stripped:
        raise KnowledgeEmbeddingError("检索问题不能为空")

    try:
        response = await _shared_client().embeddings.create(
            model=embedding_model(),
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
