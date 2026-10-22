"""录音里到底有没有人声。

上游多模态模型会对着静音编造内容：实测 1 秒静音被转成「我的天哪！」，
提示词里明确写「没有可辨识人声就返回空」之后，1 秒静音守住了，8 秒静音
又编出一句「怎么做一顿丰盛的晚餐」。所以只要能在本地确定地判断「这段
数据里没有任何采样」，就不要把它交给模型。

这里只做 WAV（手机端录的是 m4a，由 App 端的音量阈值先挡一道）。判断
不成立时返回 False/None 表示「不知道」，绝不当成「没声音」来猜。
"""

from __future__ import annotations

import struct

# 16 位采样的量化噪声通常在 ±1 上下；连续低于 64（约 -54 dBFS）的峰值
# 只可能是数字静音或极低的底噪。
SILENCE_PEAK_FLOOR = 64

NO_SPEECH_MESSAGE = "没听到声音，再说一遍。"


def _peak_of_pcm16(body: bytes) -> int:
    peak = 0
    usable = len(body) - len(body) % 2
    for (sample,) in struct.iter_unpack("<h", body[:usable]):
        magnitude = sample if sample >= 0 else -sample
        if magnitude > peak:
            peak = magnitude
            if peak >= SILENCE_PEAK_FLOOR:
                # 已经确定不静音，不必读完整段（录音最长两分钟）。
                return peak
    return peak


def wav_peak_amplitude(data: bytes) -> int | None:
    """返回 16 位 PCM WAV 的最大采样绝对值；不是这种 WAV 就返回 None。"""

    if len(data) < 44 or data[0:4] != b"RIFF" or data[8:12] != b"WAVE":
        return None

    offset = 12
    fmt_ok = False
    saw_data = False
    peak = 0
    while offset + 8 <= len(data):
        chunk_id = data[offset : offset + 4]
        (chunk_size,) = struct.unpack_from("<I", data, offset + 4)
        body_start = offset + 8
        body_end = min(body_start + chunk_size, len(data))

        if chunk_id == b"fmt ":
            if chunk_size < 16:
                return None
            audio_format, _channels, _rate, _byte_rate, _align, bits = struct.unpack_from(
                "<HHIIHH", data, body_start
            )
            # 只认 16 位 PCM；浮点 WAV 的阈值口径不一样，不猜。
            if audio_format != 1 or bits != 16:
                return None
            fmt_ok = True
        elif chunk_id == b"data":
            if not fmt_ok:
                return None
            saw_data = True
            peak = _peak_of_pcm16(data[body_start:body_end])

        offset = body_end + (chunk_size % 2)

    if not saw_data:
        return None
    return peak


def is_silent_wav(data: bytes, *, floor: int = SILENCE_PEAK_FLOOR) -> bool:
    """确定是静音时返回 True；无法判断（非 PCM WAV 等）返回 False。"""

    peak = wav_peak_amplitude(data)
    return peak is not None and peak < floor
