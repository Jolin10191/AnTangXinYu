"""把一段录音转成文字。

音频只在内存里过一遍：请求进来、转写、返回文本。不落库、不落盘、不写日志。
这是语音输入方案 A 的全部前提——用户说"我刚才差点晕过去"时，声音里带着喘，
但那声喘不该被永久保存；语音的价值是比打字容易，不是留档。
"""

import httpx

from antang_api.settings import settings


class TranscriptionError(Exception):
    """转写失败。消息会原样给用户看，所以不夹带上游的报文和状态码。"""


class NoSpeechError(TranscriptionError):
    """这段录音里没有可辨识的人声。

    单列一个类型，是因为它不是服务故障（502），而是这段输入里没有内容
    （422）；也因为它必须让用户「再说一遍」，而不是让用户「稍后再试」。
    """


async def transcribe_audio(
    data: bytes,
    *,
    filename: str,
    mime_type: str,
    client: httpx.AsyncClient | None = None,
) -> str:
    """调用中转站的 OpenAI 兼容 /audio/transcriptions。"""

    url = f"{settings.hachimi_openai_base_url}/audio/transcriptions"
    headers = {
        "Authorization": f"Bearer {settings.hachimi_api_key.get_secret_value()}",
    }
    files = {"file": (filename, data, mime_type)}
    payload = {
        "model": settings.hachimi_transcribe_model_name,
        # 用户会混着说中文和药名，明确指定语言比让模型自己猜稳。
        "language": "zh",
    }
    owned_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=settings.hachimi_transcribe_timeout_seconds)
    try:
        try:
            response = await client.post(url, headers=headers, files=files, data=payload)
        except httpx.HTTPError as exc:
            raise TranscriptionError("语音转写服务连不上，稍后再试。") from exc
        if response.status_code != httpx.codes.OK:
            raise TranscriptionError("语音转写服务这次没给出结果，稍后再试。")
        try:
            body = response.json()
        except ValueError as exc:
            raise TranscriptionError("语音转写服务返回了看不懂的内容。") from exc
        text = str(body.get("text") or "").strip()
    finally:
        if owned_client:
            await client.aclose()
    if not text:
        raise NoSpeechError("没听到声音，再说一遍。")
    return text
