from collections.abc import AsyncIterator
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from antang_api.database import get_session
from antang_api.routers.auth import router as auth_router
from antang_api.routers.voice import router as voice_router
from antang_api.settings import settings
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from antang_api.models import SpeechCue
from antang_api.voice import (
    NoSpeechError,
    SpeechCueData,
    TranscriptionError,
    VoiceTurn,
    transcribe_audio,
)


async def _client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(voice_router)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


async def _registered_headers(client: AsyncClient) -> dict[str, str]:
    registered = await client.post(
        "/api/v1/auth/register",
        json={
            "username": f"voice_{uuid4().hex[:16]}",
            "password": "correct-password",
            "consent_accepted": True,
        },
    )
    return {"Authorization": f"Bearer {registered.json()['access_token']}"}


async def test_transcribe_returns_the_text_and_sends_no_audio_onward(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """转写成功的路径：文件交给上游，回来的文字原样给客户端。"""

    upstream = AsyncMock(return_value=VoiceTurn(text="今天早上有点低血糖"))
    monkeypatch.setattr("antang_api.routers.voice.read_voice_turn", upstream)

    async for client in _client(db_session):
        headers = await _registered_headers(client)
        response = await client.post(
            "/api/v1/voice/transcribe",
            headers=headers,
            files={"file": ("voice.m4a", b"\x00\x01\x02" * 40, "audio/m4a")},
        )
        assert response.status_code == 200
        assert response.json() == {"text": "今天早上有点低血糖"}
        upstream.assert_awaited_once()
        await_args = upstream.await_args
        assert await_args is not None
        kwargs = await_args.kwargs
        assert kwargs["mime_type"] == "audio/m4a"
        assert kwargs["filename"] == "voice.m4a"
        assert len(await_args.args[0]) == 120


async def test_transcribe_rejects_files_that_are_not_audio(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream = AsyncMock(return_value=VoiceTurn(text="不该被调用"))
    monkeypatch.setattr("antang_api.routers.voice.read_voice_turn", upstream)

    async for client in _client(db_session):
        headers = await _registered_headers(client)
        response = await client.post(
            "/api/v1/voice/transcribe",
            headers=headers,
            files={"file": ("report.pdf", b"%PDF-1.4", "application/pdf")},
        )
        assert response.status_code == 415
        upstream.assert_not_awaited()


async def test_transcribe_rejects_an_empty_recording(
    db_session: AsyncSession,
) -> None:
    async for client in _client(db_session):
        headers = await _registered_headers(client)
        response = await client.post(
            "/api/v1/voice/transcribe",
            headers=headers,
            files={"file": ("voice.m4a", b"", "audio/m4a")},
        )
        assert response.status_code == 422
        assert response.json()["detail"] == "录音是空的"


async def test_transcribe_refuses_audio_over_the_size_limit(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "voice_max_audio_bytes", 8)
    upstream = AsyncMock(return_value=VoiceTurn(text="不该被调用"))
    monkeypatch.setattr("antang_api.routers.voice.read_voice_turn", upstream)

    async for client in _client(db_session):
        headers = await _registered_headers(client)
        response = await client.post(
            "/api/v1/voice/transcribe",
            headers=headers,
            files={"file": ("voice.m4a", b"\x00" * 9, "audio/m4a")},
        )
        assert response.status_code == 413
        upstream.assert_not_awaited()


async def test_transcribe_reports_upstream_failure_as_bad_gateway(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream = AsyncMock(
        side_effect=TranscriptionError("语音转写服务连不上，稍后再试。")
    )
    monkeypatch.setattr("antang_api.routers.voice.read_voice_turn", upstream)

    async for client in _client(db_session):
        headers = await _registered_headers(client)
        response = await client.post(
            "/api/v1/voice/transcribe",
            headers=headers,
            files={"file": ("voice.m4a", b"\x00" * 16, "audio/m4a")},
        )
        assert response.status_code == 502
        assert response.json()["detail"] == "语音转写服务连不上，稍后再试。"


async def test_transcribe_requires_authentication(db_session: AsyncSession) -> None:
    async for client in _client(db_session):
        response = await client.post(
            "/api/v1/voice/transcribe",
            files={"file": ("voice.m4a", b"\x00" * 16, "audio/m4a")},
        )
        assert response.status_code == 401


async def test_transcribe_audio_sends_the_openai_shape() -> None:
    """一次真实形状的请求：Bearer、model、language: zh、文件字段名 file。"""

    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("authorization")
        seen["content_type"] = request.headers.get("content-type")
        seen["body"] = request.read()
        return httpx.Response(200, json={"text": "  我头晕  "})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        text = await transcribe_audio(
            b"fake-m4a",
            filename="voice.m4a",
            mime_type="audio/m4a",
            client=client,
        )

    assert text == "我头晕"
    assert seen["url"] == f"{settings.hachimi_openai_base_url}/audio/transcriptions"
    assert seen["authorization"] == (
        f"Bearer {settings.hachimi_api_key.get_secret_value()}"
    )
    assert str(seen["content_type"]).startswith("multipart/form-data")
    body = seen["body"]
    assert isinstance(body, bytes)
    assert b'name="model"' in body
    assert settings.hachimi_transcribe_model_name.encode() in body
    assert b'name="language"' in body
    assert b"zh" in body
    assert b'name="file"' in body
    assert b'filename="voice.m4a"' in body
    assert b"fake-m4a" in body


async def test_transcribe_audio_hides_upstream_details() -> None:
    """上游报错不许把状态码或报文透给用户：那不是用户能修的东西。"""

    def failing(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "internal"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(failing)) as client:
        with pytest.raises(TranscriptionError) as error:
            await transcribe_audio(
                b"fake-m4a",
                filename="voice.m4a",
                mime_type="audio/m4a",
                client=client,
            )
    assert "500" not in str(error.value)
    assert "internal" not in str(error.value)


async def test_transcribe_audio_treats_white_space_as_no_speech() -> None:
    def silent(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"text": "   "})

    async with httpx.AsyncClient(transport=httpx.MockTransport(silent)) as client:
        with pytest.raises(TranscriptionError):
            await transcribe_audio(
                b"fake-m4a",
                filename="voice.m4a",
                mime_type="audio/m4a",
                client=client,
            )


async def test_transcribe_audio_survives_a_dead_upstream() -> None:
    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(unreachable)) as client:
        with pytest.raises(TranscriptionError) as error:
            await transcribe_audio(
                b"fake-m4a",
                filename="voice.m4a",
                mime_type="audio/m4a",
                client=client,
            )
    assert str(error.value) == "语音转写服务连不上，稍后再试。"


async def test_transcribe_keeps_the_cue_for_the_next_turn(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """配置了音频模型时，转写这一趟顺手把声音状态存下来给下一轮用。"""

    monkeypatch.setattr(settings, "hachimi_audio_model_name", "gemini-3.8-flash")
    cue = SpeechCueData(pace="fast", energy="low", breathing="audible", confidence=0.6)
    upstream = AsyncMock(return_value=VoiceTurn(text="我今天不敢睡", cue=cue))
    monkeypatch.setattr("antang_api.routers.voice.read_voice_turn", upstream)

    async for client in _client(db_session):
        headers = await _registered_headers(client)
        response = await client.post(
            "/api/v1/voice/transcribe",
            headers=headers,
            files={"file": ("voice.m4a", b"\x00" * 16, "audio/m4a")},
        )
        assert response.status_code == 200
        assert response.json() == {"text": "我今天不敢睡"}

    cues = (await db_session.scalars(select(SpeechCue))).all()
    assert len(cues) == 1
    assert cues[0].pace == "fast"
    assert cues[0].energy == "low"
    assert cues[0].model_name == "gemini-3.8-flash"
    assert cues[0].consumed_at is None


async def test_transcribe_stores_no_cue_when_there_is_none(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream = AsyncMock(return_value=VoiceTurn(text="只有文字"))
    monkeypatch.setattr("antang_api.routers.voice.read_voice_turn", upstream)

    async for client in _client(db_session):
        headers = await _registered_headers(client)
        response = await client.post(
            "/api/v1/voice/transcribe",
            headers=headers,
            files={"file": ("voice.m4a", b"\x00" * 16, "audio/m4a")},
        )
        assert response.status_code == 200

    assert (await db_session.scalars(select(SpeechCue))).all() == []


async def test_a_cue_that_cannot_be_stored_does_not_lose_the_transcript(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """声音状态是附加信息：存不上也要把文字给用户，但必须留下痕迹。"""

    cue = SpeechCueData(pace="slow", energy="low", breathing="none", confidence=0.4)
    monkeypatch.setattr(
        "antang_api.routers.voice.read_voice_turn",
        AsyncMock(return_value=VoiceTurn(text="还得能发出去", cue=cue)),
    )

    async def broken(*args: object, **kwargs: object) -> object:
        raise SQLAlchemyError("disk is full")

    monkeypatch.setattr("antang_api.routers.voice.record_speech_cue", broken)

    async for client in _client(db_session):
        headers = await _registered_headers(client)
        response = await client.post(
            "/api/v1/voice/transcribe",
            headers=headers,
            files={"file": ("voice.m4a", b"\x00" * 16, "audio/m4a")},
        )
        assert response.status_code == 200
        assert response.json() == {"text": "还得能发出去"}


def _pcm16_wav(samples: bytes) -> bytes:
    """最小的 16 位单声道 WAV，够让静音闸读到 data 块。"""

    header = b"RIFF" + (36 + len(samples)).to_bytes(4, "little") + b"WAVEfmt "
    header += (16).to_bytes(4, "little") + (1).to_bytes(2, "little")
    header += (1).to_bytes(2, "little") + (16000).to_bytes(4, "little")
    header += (32000).to_bytes(4, "little") + (2).to_bytes(2, "little")
    header += (16).to_bytes(2, "little") + b"data" + len(samples).to_bytes(4, "little")
    return header + samples


async def test_a_silent_recording_never_reaches_the_model(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """静音不交给上游：它会对静音编出一整句话，那比报错更糟。"""

    upstream = AsyncMock(return_value=VoiceTurn(text="不该被调用"))
    monkeypatch.setattr("antang_api.routers.voice.read_voice_turn", upstream)

    async for client in _client(db_session):
        headers = await _registered_headers(client)
        response = await client.post(
            "/api/v1/voice/transcribe",
            headers=headers,
            files={
                "file": (
                    "voice.wav",
                    _pcm16_wav(b"\x00\x00" * 16000),
                    "audio/wav",
                )
            },
        )
        assert response.status_code == 422
        assert response.json()["detail"] == "没听到声音，再说一遍。"
        upstream.assert_not_awaited()


async def test_no_speech_from_the_model_is_a_422_not_a_server_error(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """模型判定没有人声时，用户要的是「再说一遍」，不是「稍后再试」。"""

    monkeypatch.setattr(
        "antang_api.routers.voice.read_voice_turn",
        AsyncMock(side_effect=NoSpeechError("没听到声音，再说一遍。")),
    )

    async for client in _client(db_session):
        headers = await _registered_headers(client)
        response = await client.post(
            "/api/v1/voice/transcribe",
            headers=headers,
            files={"file": ("voice.m4a", b"\x00" * 16, "audio/m4a")},
        )
        assert response.status_code == 422
        assert response.json()["detail"] == "没听到声音，再说一遍。"
