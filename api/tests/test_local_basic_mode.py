from uuid import uuid4
from typing import Any

from httpx import AsyncClient
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from antang_api.main import app, lifespan
from antang_api.models import Message
from antang_api.settings import Settings, settings


def test_basic_mode_is_explicit_and_full_mode_requires_credentials() -> None:
    values: dict[str, Any] = dict(
        _env_file=None,
        hachimi_api_key="",
        hachimi_model_name="",
        hachimi_base_url="",
        tavily_api_key="",
        hindsight_mode="disabled",
        database_url=settings.database_url,
        jwt_secret="local-test-only-secret-at-least-32-characters",
        access_token_minutes=15,
        refresh_token_days=30,
    )
    assert Settings(local_basic_mode=True, **values).local_basic_mode
    with pytest.raises(ValueError, match="完整模式缺少配置"):
        Settings(local_basic_mode=False, **values)


async def test_basic_mode_keeps_accounts_and_history_but_does_not_create_ai_runs(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "local_basic_mode", True)
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "consent_accepted": True,
            "username": f"local_{uuid4().hex[:12]}",
            "password": "local-test-password",
        },
    )
    assert response.status_code == 201
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    response = await client.post(
        "/api/v1/chat/messages",
        headers=headers,
        json={
            "client_message_id": str(uuid4()),
            "content": "测试本地聊天",
        },
    )
    assert response.status_code == 503
    assert "智能聊天尚未配置" in response.json()["detail"]
    assert await db_session.scalar(select(Message.id)) is None
    assert (
        await client.get("/api/v1/chat/messages", headers=headers)
    ).status_code == 200
    assert (
        await client.get("/api/v1/health-profile", headers=headers)
    ).status_code == 200
    assert (await client.get("/health")).json()["mode"] == "local-basic"


async def test_basic_startup_does_not_initialize_external_ai_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "local_basic_mode", True)

    def unexpected_client(*args, **kwargs):
        raise AssertionError("基础联调不应创建 Hindsight 客户端")

    monkeypatch.setattr("antang_api.main.Hindsight", unexpected_client)
    async with lifespan(app):
        pass
