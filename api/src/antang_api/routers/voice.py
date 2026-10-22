from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from antang_api.database import get_session
from antang_api.models import User
from antang_api.patient_access import get_patient_user
from antang_api.settings import settings
from antang_api.voice import (
    NoSpeechError,
    TranscriptionError,
    read_voice_turn,
    record_speech_cue,
)
from antang_api.voice.silence import NO_SPEECH_MESSAGE, is_silent_wav

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])

# 移动端录的是 m4a；浏览器和测试环境可能是 wav/webm，一并放行。
# 不做编解码校验：容器头对不上时上游会拒绝，这比我们自己写嗅探可靠。
SUPPORTED_AUDIO_TYPES = frozenset(
    {
        "audio/aac",
        "audio/m4a",
        "audio/mp4",
        "audio/mpeg",
        "audio/ogg",
        "audio/wav",
        "audio/webm",
        "audio/x-m4a",
        "audio/x-wav",
    }
)


class TranscriptionResponse(BaseModel):
    text: str


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(
    file: Annotated[UploadFile, File()],
    user: Annotated[User, Depends(get_patient_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TranscriptionResponse:
    """把一段语音转成文字。音频只在内存里过一遍，不保存。

    配了 HACHIMI_AUDIO_MODEL_NAME 时，同一次请求还会带回声音的粗状态（快慢、
    轻重、有没有喘）；没有就只做转写。声音状态存不存得上都不影响这次转写。
    """

    if settings.local_basic_mode:
        raise HTTPException(503, "当前为本地基础联调，语音服务尚未配置")

    mime_type = (file.content_type or "").split(";")[0].strip().lower()
    if mime_type not in SUPPORTED_AUDIO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="只支持音频文件",
        )
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="录音是空的")
    if len(data) > settings.voice_max_audio_bytes:
        raise HTTPException(status_code=413, detail="录音太长了，分两段说给我听")
    # 上游对静音会编造内容（实测 8 秒静音转出「怎么做一顿丰盛的晚餐」），
    # 所以能确定是静音时就不要问它。只认 16 位 PCM WAV；m4a 由 App 端的
    # 音量阈值先挡一道，这里判断不了就不猜。
    if is_silent_wav(data):
        raise HTTPException(status_code=422, detail=NO_SPEECH_MESSAGE)
    try:
        turn = await read_voice_turn(
            data,
            filename=(file.filename or "voice.m4a").strip()[:255] or "voice.m4a",
            mime_type=mime_type,
        )
    except NoSpeechError as exc:
        # 422：这段输入里没有人声，不是上游故障，用户重说一遍就行。
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except TranscriptionError as exc:
        # 502：错在转写上游，不是用户说错了，别让客户端以为请求本身有问题。
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if turn.cue is not None:
        try:
            await record_speech_cue(
                session,
                user_id=user.id,
                cue=turn.cue,
                model_name=settings.hachimi_audio_model_name.strip(),
            )
            await session.commit()
        except SQLAlchemyError:
            # 声音状态是可选的附加信息：存不上就只返回转写，但要留痕，
            # 不能让"每次都没存上"变成没人知道的事实。
            await session.rollback()
            logger.opt(exception=True).warning("声音状态没存上，只返回转写")
    return TranscriptionResponse(text=turn.text)
