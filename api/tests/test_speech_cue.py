import base64
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from antang_api.models import User
from antang_api.settings import settings
from antang_api.voice import (
    NoSpeechError,
    SpeechCueData,
    TranscriptionError,
    VoiceTurn,
    mark_speech_cue_consumed,
    parse_voice_reply,
    pending_speech_cue,
    read_voice_turn,
    record_speech_cue,
    render_speech_cue,
)


async def _create_user(db_session: AsyncSession, prefix: str) -> User:
    username = f"{prefix}_{uuid4().hex[:12]}"
    user = User(
        username=username,
        username_normalized=username,
        password_hash="test-only-password-hash",
    )
    db_session.add(user)
    await db_session.flush()
    return user


def test_parse_reads_the_transcript_and_how_it_was_said() -> None:
    reply = json.dumps(
        {
            "transcript": "  我刚才有点慌  ",
            "speech": {
                "pace": "fast",
                "energy": "low",
                "breathing": "audible",
                "confidence": 0.72,
            },
        }
    )

    text, cue = parse_voice_reply(reply)

    assert text == "我刚才有点慌"
    assert cue == SpeechCueData(
        pace="fast",
        energy="low",
        breathing="audible",
        confidence=0.72,
    )


def test_parse_refuses_a_speech_block_without_confidence() -> None:
    """没有置信度的听感，等于没有听感。"""

    text, cue = parse_voice_reply(
        json.dumps({"transcript": "还行", "speech": {"pace": "fast"}})
    )

    assert text == "还行"
    assert cue is None


def test_parse_drops_a_cue_that_says_nothing() -> None:
    text, cue = parse_voice_reply(
        json.dumps(
            {
                "transcript": "嗯",
                "speech": {
                    "pace": "unknown",
                    "energy": "unknown",
                    "breathing": "unknown",
                    "confidence": 0.9,
                },
            }
        )
    )

    assert text == "嗯"
    assert cue is None


def test_parse_survives_a_fenced_reply() -> None:
    reply = '```json\n{"transcript": "好", "speech": null}\n```'

    text, cue = parse_voice_reply(reply)

    assert text == "好"
    assert cue is None


def test_parse_keeps_speech_null_as_no_cue() -> None:
    text, cue = parse_voice_reply('{"transcript": "", "speech": null}')

    assert text == ""
    assert cue is None


def test_parse_refuses_a_reply_without_json() -> None:
    with pytest.raises(TranscriptionError) as error:
        parse_voice_reply("好的，我听清了")

    assert str(error.value) == "语音服务返回了看不懂的内容，稍后再试。"


def test_confidence_is_clamped_into_a_range() -> None:
    _, cue = parse_voice_reply(
        json.dumps(
            {
                "transcript": "在",
                "speech": {
                    "pace": "slow",
                    "energy": "normal",
                    "breathing": "none",
                    "confidence": 4.5,
                },
            }
        )
    )

    assert cue is not None
    assert cue.confidence == 1.0


def test_render_marks_the_cue_as_a_guess() -> None:
    rendered = render_speech_cue(
        SpeechCueData(pace="fast", energy="low", breathing="audible", confidence=0.7)
    )

    assert rendered.startswith("[语音状态]")
    assert "置信度 0.70" in rendered
    assert "语速偏快" in rendered
    assert "声音偏轻" in rendered
    assert "呼吸声可闻" in rendered
    # 这几句是这个功能能不能上线的前提：不许外显、不许当诊断、不跟用户的话抢。
    assert "不要提到你听到了什么声音" in rendered
    assert "不要说「你听起来很焦虑」" in rendered
    assert "以说的话为准" in rendered


def test_render_says_so_when_nothing_could_be_heard() -> None:
    rendered = render_speech_cue(
        SpeechCueData(
            pace="unknown",
            energy="unknown",
            breathing="unknown",
            confidence=0.2,
        )
    )

    assert "说不准" in rendered


async def test_a_cue_is_recorded_then_consumed(db_session: AsyncSession) -> None:
    user = await _create_user(db_session, "cue")
    cue = SpeechCueData(pace="slow", energy="low", breathing="none", confidence=0.5)

    row = await record_speech_cue(
        db_session,
        user_id=user.id,
        cue=cue,
        model_name="gemini-3.8-flash",
    )
    await db_session.commit()

    pending = await pending_speech_cue(db_session, user_id=user.id)
    assert pending is not None
    assert pending.id == row.id
    assert pending.pace == "slow"
    assert pending.expires_at > pending.heard_at

    await mark_speech_cue_consumed(db_session, cue_id=row.id)
    await db_session.commit()

    assert await pending_speech_cue(db_session, user_id=user.id) is None


async def test_an_expired_cue_is_not_pending(db_session: AsyncSession) -> None:
    user = await _create_user(db_session, "cue_expired")
    cue = SpeechCueData(pace="fast", energy="high", breathing="audible", confidence=0.4)

    await record_speech_cue(
        db_session,
        user_id=user.id,
        cue=cue,
        model_name="gemini-3.8-flash",
        now=datetime.now(UTC) - timedelta(minutes=20),
    )
    await db_session.commit()

    assert await pending_speech_cue(db_session, user_id=user.id) is None


async def test_pending_never_returns_another_users_cue(
    db_session: AsyncSession,
) -> None:
    mine = await _create_user(db_session, "cue_mine")
    theirs = await _create_user(db_session, "cue_theirs")
    cue = SpeechCueData(pace="slow", energy="normal", breathing="none", confidence=0.6)

    await record_speech_cue(
        db_session, user_id=theirs.id, cue=cue, model_name="gemini-3.8-flash"
    )
    await db_session.commit()

    assert await pending_speech_cue(db_session, user_id=mine.id) is None
    assert await pending_speech_cue(db_session, user_id=theirs.id) is not None


async def test_without_an_audio_model_only_the_text_comes_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "hachimi_audio_model_name", "")
    seen: dict[str, object] = {}

    async def fake_transcribe(
        data: bytes, *, filename: str, mime_type: str, client: object = None
    ) -> str:
        seen["mime_type"] = mime_type
        return "只转写"

    monkeypatch.setattr("antang_api.voice.speech_cue.transcribe_audio", fake_transcribe)

    turn = await read_voice_turn(
        b"\x00\x01" * 8, filename="voice.m4a", mime_type="audio/m4a"
    )

    assert turn == VoiceTurn(text="只转写", cue=None)
    assert seen["mime_type"] == "audio/m4a"


async def test_an_audio_model_returns_text_and_a_cue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "hachimi_audio_model_name", "gemini-3.8-flash")
    seen: dict[str, object] = {}
    reply = json.dumps(
        {
            "transcript": "我今天不敢睡觉",
            "speech": {
                "pace": "slow",
                "energy": "low",
                "breathing": "audible",
                "confidence": 0.6,
            },
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.read())
        return httpx.Response(
            200, json={"choices": [{"message": {"content": reply}}]}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        turn = await read_voice_turn(
            b"\x00\x01" * 8,
            filename="voice.m4a",
            mime_type="audio/m4a",
            client=client,
        )

    assert turn.text == "我今天不敢睡觉"
    assert turn.cue is not None
    assert turn.cue.pace == "slow"
    assert seen["url"] == f"{settings.hachimi_openai_base_url}/chat/completions"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["model"] == "gemini-3.8-flash"
    assert body["temperature"] == 0
    audio = body["messages"][1]["content"][1]
    assert audio["type"] == "input_audio"
    assert audio["input_audio"]["format"] == "aac"
    assert base64.b64decode(audio["input_audio"]["data"]) == b"\x00\x01" * 8


async def test_silence_comes_back_as_nothing_heard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """静音时上游会编造内容；只要转写为空，就当没听清，绝不往下传。"""

    monkeypatch.setattr(settings, "hachimi_audio_model_name", "gemini-3.8-flash")
    reply = json.dumps({"transcript": "", "speech": None})

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": reply}}]}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(TranscriptionError) as error:
            await read_voice_turn(
                b"\x00" * 16,
                filename="voice.m4a",
                mime_type="audio/m4a",
                client=client,
            )

    assert str(error.value) == "没听到声音，再说一遍。"


async def test_heard_speech_false_wins_over_a_transcript(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """模型自己说没听到人声时，它顺手编出的转写不能采信。

    实测同一段静音：1 秒能守住空转写，8 秒会返回
    {"heard_speech": true, "transcript": "怎么做一顿丰盛的晚餐"}，
    所以既要听 heard_speech，也要在本地先挡掉确定是静音的录音。
    """

    monkeypatch.setattr(settings, "hachimi_audio_model_name", "gemini-3.8-flash")
    reply = json.dumps(
        {"heard_speech": False, "transcript": "我的天哪！", "speech": None}
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": reply}}]}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(NoSpeechError) as error:
            await read_voice_turn(
                b"\x00" * 16,
                filename="voice.m4a",
                mime_type="audio/m4a",
                client=client,
            )

    assert str(error.value) == "没听到声音，再说一遍。"


def test_parse_raises_no_speech_when_the_model_heard_nothing() -> None:
    reply = json.dumps({"heard_speech": False, "transcript": "", "speech": None})
    with pytest.raises(NoSpeechError):
        parse_voice_reply(reply)
