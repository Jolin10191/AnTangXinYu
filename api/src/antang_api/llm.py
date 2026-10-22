from langchain_openai import ChatOpenAI

from antang_api.settings import settings


def _build_model(*, streaming: bool, model_name: str | None = None) -> ChatOpenAI:
    return ChatOpenAI(
        model=model_name or settings.hachimi_model_name,
        api_key=settings.hachimi_api_key,
        base_url=settings.hachimi_openai_base_url,
        timeout=settings.hachimi_timeout_seconds,
        max_completion_tokens=settings.hachimi_max_output_tokens,
        max_retries=0,
        streaming=streaming,
        stream_usage=streaming,
    )


def build_chat_model() -> ChatOpenAI:
    """创建用于 Core Agent 用户可见流式回复的模型。"""

    return _build_model(streaming=True)


def build_non_streaming_model() -> ChatOpenAI:
    """创建用于内部 Sub-agent、不会向聊天流发送 token 的模型。"""

    return _build_model(streaming=False)


def build_proactive_care_model() -> ChatOpenAI:
    """创建主动关怀 worker 使用的模型。

    对话和主动关怀可以各自选模型：对话再慢用户也能追问，主动关怀是深夜自己
    发出去的，所以宁可让它慢一点，也别换一个质量更差的。没配
    HACHIMI_PROACTIVE_MODEL_NAME 时回退到对话模型。
    """

    return _build_model(
        streaming=False,
        model_name=settings.resolved_proactive_model_name,
    )
