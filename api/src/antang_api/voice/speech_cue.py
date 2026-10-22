"""从一段录音里读出「怎么说的」，而不只是「说了什么」。

音频只在这里过一遍：进来、读一次、留下几个标量，然后丢掉。不做声学情绪识别
模型，只让多模态模型给出粗粒度听感（快慢、轻重、有没有喘），并且带着它自己的
置信度一起存下来——低置信是信息，不是要抹掉的噪声。

为什么这么保守：低血糖本身会改变声音（喘、发虚、语速乱），把它当成"焦虑"来
判断，代价是当着一个正在低血糖的人说他看起来焦虑。所以这里只写「听感」，
不写「情绪」，而且永远标着置信度。
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass

import httpx

from antang_api.models import SPEECH_BREATHING, SPEECH_ENERGIES, SPEECH_PACES
from antang_api.settings import settings
from antang_api.voice.silence import NO_SPEECH_MESSAGE
from antang_api.voice.transcription import (
    NoSpeechError,
    TranscriptionError,
    transcribe_audio,
)

# 声音状态对紧接着的那一句话有意义。窗口比一场对话里的一次停顿长一点，
# 但短到不会把上一段话题的语气带到下一段。
SPEECH_CUE_WINDOW_SECONDS = 600

_AUDIO_FORMATS: dict[str, str] = {
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/mpeg": "mp3",
    "audio/m4a": "aac",
    "audio/x-m4a": "aac",
    "audio/mp4": "aac",
    "audio/aac": "aac",
    "audio/ogg": "ogg",
}

CUES_PROMPT = """你要做两件事，只输出一个 JSON 对象，不要任何解释，不要代码块：

1. 先判断这段录音里有没有可辨识的人声，放在 "heard_speech" 里（true 或 false）。
   静音、只有噪声、只有音乐、只有呼吸声，都算 false。
2. 转写这段录音里用户说的话（中文），放在 "transcript" 里。听不清的地方用「…」。
   "heard_speech" 是 false 时，"transcript" 必须是空字符串，不要编造内容。
3. 判断用户说话的方式，放在 "speech" 里；这不是情绪诊断，只是听感：
   "pace" 取 slow / normal / fast / unknown（语速），
   "energy" 取 low / normal / high / unknown（音量与力度），
   "breathing" 取 audible / none / unknown（是否听得到呼吸或换气），
   "confidence" 是 0 到 1 之间的小数，表示你对 speech 这一项判断的把握。
   判断不了就写 "speech": null，不要猜。

整段录音里没有可辨识的人声时（静音、只有噪声、只有音乐），
"transcript" 写空字符串，"speech" 写 null。不要编造内容。"""


@dataclass(frozen=True)
class SpeechCueData:
    pace: str
    energy: str
    breathing: str
    confidence: float


@dataclass(frozen=True)
class VoiceTurn:
    """一次语音输入的产物：转写文本 + 可选的声音状态。"""

    text: str
    cue: SpeechCueData | None = None


def _pick(value: object, allowed: tuple[str, ...]) -> str:
    text = value.strip().lower() if isinstance(value, str) else ""
    return text if text in allowed else "unknown"


def parse_voice_reply(reply: str) -> tuple[str, SpeechCueData | None]:
    """把模型回复解析成 (转写, 声音状态)。

    解析失败按「没听清」处理：宁可让用户再说一遍，也不要拿半截 JSON 拼出一句
    用户根本没说过的话。
    """

    stripped = reply.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        stripped = "\n".join(line for line in lines if not line.strip().startswith("```"))
    start, end = stripped.find("{"), stripped.rfind("}")
    if start == -1 or end <= start:
        raise TranscriptionError("语音服务返回了看不懂的内容，稍后再试。")
    try:
        payload = json.loads(stripped[start : end + 1])
    except ValueError as exc:
        raise TranscriptionError("语音服务返回了看不懂的内容，稍后再试。") from exc
    if not isinstance(payload, dict):
        raise TranscriptionError("语音服务返回了看不懂的内容，稍后再试。")

    transcript = payload.get("transcript")
    text = transcript.strip() if isinstance(transcript, str) else ""
    # heard_speech 明确说没有时，转写里出现什么都不能信：实测同一段静音，
    # 1 秒能守住空转写，8 秒又编出一句完整的话。
    if payload.get("heard_speech") is False:
        raise NoSpeechError(NO_SPEECH_MESSAGE)
    speech = payload.get("speech")
    if not isinstance(speech, dict):
        return text, None

    confidence = speech.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        return text, None
    confidence = min(max(float(confidence), 0.0), 1.0)
    cue = SpeechCueData(
        pace=_pick(speech.get("pace"), SPEECH_PACES),
        energy=_pick(speech.get("energy"), SPEECH_ENERGIES),
        breathing=_pick(speech.get("breathing"), SPEECH_BREATHING),
        confidence=round(confidence, 2),
    )
    # 三项全是 unknown 的 cue 没有任何信息量，存下来只会让下一轮多一段噪声。
    if cue.pace == cue.energy == cue.breathing == "unknown":
        return text, None
    return text, cue


_PACE_WORDS = {"slow": "语速偏慢", "fast": "语速偏快"}
_ENERGY_WORDS = {"low": "声音偏轻", "high": "声音偏响"}
_BREATHING_WORDS = {"audible": "呼吸声可闻", "none": "听不到明显呼吸声"}


def render_speech_cue(cue: SpeechCueData) -> str:
    """把声音状态写成给模型看的内部指令。"""

    observed = [
        _PACE_WORDS.get(cue.pace, ""),
        _ENERGY_WORDS.get(cue.energy, ""),
        _BREATHING_WORDS.get(cue.breathing, ""),
    ]
    described = "、".join(word for word in observed if word) or "说不准"
    return (
        "[语音状态]\n"
        "这句话是用户用语音说的。下面是从那一小段声音里读出的粗状态"
        f"（置信度 {cue.confidence:.2f}）：{described}。\n"
        "它只是听感，不是诊断，也可能被低血糖本身的症状带偏。只拿它调整语气和"
        "追问方式；不要提到你听到了什么声音，不要说「你听起来很焦虑」，也不要"
        "据此下任何判断。与用户说出口的话冲突时，以说的话为准。"
    )


async def _ask_audio_model(
    data: bytes,
    *,
    mime_type: str,
    client: httpx.AsyncClient,
) -> str:
    url = f"{settings.hachimi_openai_base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.hachimi_api_key.get_secret_value()}",
    }
    payload = {
        "model": settings.hachimi_audio_model_name.strip(),
        "temperature": 0,
        "messages": [
            {"role": "system", "content": CUES_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "转写这段录音，并按格式输出 JSON。"},
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": base64.b64encode(data).decode("ascii"),
                            "format": _AUDIO_FORMATS.get(mime_type, "wav"),
                        },
                    },
                ],
            },
        ],
    }
    try:
        response = await client.post(
            url,
            headers=headers,
            json=payload,
            timeout=settings.hachimi_transcribe_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise TranscriptionError("语音服务连不上，稍后再试。") from exc
    if response.status_code != httpx.codes.OK:
        raise TranscriptionError("语音服务这次没给出结果，稍后再试。")
    try:
        body = response.json()
    except ValueError as exc:
        raise TranscriptionError("语音服务返回了看不懂的内容，稍后再试。") from exc
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise TranscriptionError("语音服务返回了看不懂的内容，稍后再试。")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, list):
        content = "".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        )
    if not isinstance(content, str) or not content.strip():
        raise TranscriptionError("没有听清，再说一遍试试。")
    return content


async def read_voice_turn(
    data: bytes,
    *,
    filename: str,
    mime_type: str,
    client: httpx.AsyncClient | None = None,
) -> VoiceTurn:
    """读一次语音：配了音频模型就顺便带回声音状态，否则只做转写。"""

    if not settings.hachimi_audio_model_name.strip():
        text = await transcribe_audio(
            data,
            filename=filename,
            mime_type=mime_type,
            client=client,
        )
        return VoiceTurn(text=text, cue=None)

    owned_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=settings.hachimi_transcribe_timeout_seconds)
    try:
        reply = await _ask_audio_model(data, mime_type=mime_type, client=client)
    finally:
        if owned_client:
            await client.aclose()
    text, cue = parse_voice_reply(reply)
    if not text:
        raise NoSpeechError(NO_SPEECH_MESSAGE)
    return VoiceTurn(text=text, cue=cue)
