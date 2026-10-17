from typing import Literal, Self
from urllib.parse import urlsplit, urlunsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """从.env文件中读取配置"""

    hachimi_api_key: SecretStr = Field(min_length=1)
    hachimi_model_name: str = Field(min_length=1)
    hachimi_base_url: str = Field(min_length=1)
    hachimi_timeout_seconds: float = Field(default=300, gt=0)
    hachimi_max_output_tokens: int = Field(default=4096, gt=0)

    # 知识库检索的向量化独立于对话模型：留空时沿用 HACHIMI_*，填了就各走各的。
    # 拆开的原因是同一个 key 同时承担对话、记忆抽取和向量化，任一处欠费会全线停摆。
    knowledge_embedding_api_key: SecretStr | None = None
    knowledge_embedding_base_url: str = ""
    knowledge_embedding_model: str = "bge-m3"

    tavily_api_key: SecretStr = Field(min_length=1)
    # Tavily 没有承诺最终字符串的总上限；以下是项目自己的初始安全边界。
    tavily_search_max_snippet_chars: int = Field(default=2_000, gt=0)
    tavily_fetch_max_content_chars: int = Field(default=10_000, gt=0)

    hindsight_mode: Literal["disabled", "shadow", "online"] = "disabled"
    hindsight_base_url: str = "http://127.0.0.1:8888"
    hindsight_api_key: SecretStr | None = None
    hindsight_timeout_seconds: float = Field(default=300, gt=0)
    hindsight_retain_user_turns: int = Field(default=3, gt=0)
    hindsight_recall_budget: Literal["low", "mid", "high"] = "low"
    hindsight_recall_max_tokens: int = Field(default=2_048, gt=0)

    database_url: str = Field(pattern=r"^postgresql\+psycopg://")
    jwt_secret: SecretStr = Field(min_length=32)
    access_token_minutes: int = Field(gt=0)
    refresh_token_days: int = Field(gt=0)

    proactive_care_worker_poll_seconds: float = Field(default=5, gt=0)
    proactive_care_lease_minutes: int = Field(default=20, gt=0)
    proactive_care_max_attempts: int = Field(default=3, gt=0)
    proactive_care_retry_seconds: int = Field(default=60, gt=0)

    expo_push_access_token: SecretStr | None = None
    expo_push_timeout_seconds: float = Field(default=15, gt=0)
    push_delivery_worker_poll_seconds: float = Field(default=5, gt=0)
    push_delivery_lease_seconds: int = Field(default=60, gt=0)
    push_delivery_max_attempts: int = Field(default=5, gt=0)
    push_delivery_retry_seconds: int = Field(default=30, gt=0)
    push_receipt_delay_seconds: int = Field(default=900, gt=0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # 允许旧 .env 在迁移期间保留已经不再读取的供应商变量。
        extra="ignore",
    )

    # 输入达到 150000 token触发压缩
    context_compaction_trigger_tokens: int = Field(
        default=150_000,
        gt=0,
    )

    # 保留20条原始消息
    context_recent_messages_to_keep: int = Field(
        default=20,
        gt=0,
    )

    # 工具结果先于对话摘要清理，避免已经失效的大段网页内容占满上下文。
    context_tool_result_cleanup_trigger_tokens: int = Field(
        default=100_000,
        gt=0,
    )
    context_recent_tool_results_to_keep: int = Field(
        default=3,
        gt=0,
    )

    # 一轮对话中限制模型连续调用工具的次数和单次并行数量。
    agent_max_tool_rounds: int = Field(default=10, gt=0)
    agent_max_parallel_tool_calls: int = Field(default=5, gt=0)

    @property
    def langgraph_database_url(self) -> str:
        """把 SQLAlchemy 的地址转换成 psycopg 直接使用的地址"""
        sqlalchemy_prefix = "postgresql+psycopg://"
        return "postgresql://" + self.database_url.removeprefix(sqlalchemy_prefix)

    @property
    def hachimi_openai_base_url(self) -> str:
        """把配置中的完整 Chat Completions 地址转换成 SDK 的基础地址。"""

        parsed = urlsplit(self.hachimi_base_url)
        path = "/" + "/".join(part for part in parsed.path.split("/") if part)
        value = urlunsplit((parsed.scheme, parsed.netloc, path, "", "")).rstrip("/")
        suffix = "/chat/completions"
        if value.endswith(suffix):
            value = value[: -len(suffix)]
        return value

    @property
    def knowledge_embedding_openai_base_url(self) -> str:
        """向量化服务的基础地址；没有单独配置时复用对话中转站。"""

        configured = self.knowledge_embedding_base_url.strip()
        if not configured:
            return self.hachimi_openai_base_url
        parsed = urlsplit(configured)
        path = "/" + "/".join(part for part in parsed.path.split("/") if part)
        value = urlunsplit((parsed.scheme, parsed.netloc, path, "", "")).rstrip("/")
        suffix = "/chat/completions"
        if value.endswith(suffix):
            value = value[: -len(suffix)]
        return value

    @property
    def resolved_knowledge_embedding_api_key(self) -> str:
        """向量化用哪把钥匙：单独配了就用自己的，否则回退到对话钥匙。"""

        if self.knowledge_embedding_api_key is not None:
            value = self.knowledge_embedding_api_key.get_secret_value()
            if value:
                return value
        return self.hachimi_api_key.get_secret_value()

    @model_validator(mode="after")
    def validate_hindsight(self) -> Self:
        if self.hindsight_mode != "disabled" and (
            self.hindsight_api_key is None
            or not self.hindsight_api_key.get_secret_value()
        ):
            raise ValueError("启用 Hindsight 时必须配置 HINDSIGHT_API_KEY")
        if self.expo_push_timeout_seconds >= self.push_delivery_lease_seconds:
            raise ValueError("Expo Push HTTP 超时必须短于发送租约")
        return self


settings = Settings()  # pyright: ignore[reportCallIssue]
