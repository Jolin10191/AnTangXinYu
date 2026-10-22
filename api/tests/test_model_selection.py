"""对话与主动关怀可以各用一个模型。"""

from __future__ import annotations

import pytest

from antang_api import llm
from antang_api.settings import Settings


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "hachimi_api_key": "test-key",
        "hachimi_model_name": "chat-model",
        "hachimi_proactive_model_name": "",
        "hachimi_base_url": "http://127.0.0.1:1/chat/completions",
        "tavily_api_key": "test-only-tavily-key",
        "database_url": "postgresql+psycopg://postgres@localhost/antang",
        "jwt_secret": "0" * 32,
        "access_token_minutes": 30,
        "refresh_token_days": 7,
    }
    values.update(overrides)
    return Settings(**values)  # pyright: ignore[reportArgumentType]


def test_proactive_model_falls_back_to_the_chat_model() -> None:
    assert _settings().resolved_proactive_model_name == "chat-model"


def test_proactive_model_overrides_the_chat_model() -> None:
    settings = _settings(hachimi_proactive_model_name="proactive-model")

    assert settings.resolved_proactive_model_name == "proactive-model"


def test_blank_proactive_name_still_falls_back() -> None:
    settings = _settings(hachimi_proactive_model_name="   ")

    assert settings.resolved_proactive_model_name == "chat-model"


def test_builders_pick_the_right_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        llm,
        "settings",
        _settings(hachimi_proactive_model_name="proactive-model"),
    )

    assert llm.build_chat_model().model_name == "chat-model"
    assert llm.build_non_streaming_model().model_name == "chat-model"
    assert llm.build_proactive_care_model().model_name == "proactive-model"
