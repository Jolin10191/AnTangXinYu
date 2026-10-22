"""本地静音判断：静音不交给上游模型，因为它会编出用户没说过的话。"""

import struct

import pytest

from antang_api.voice.silence import (
    SILENCE_PEAK_FLOOR,
    is_silent_wav,
    wav_peak_amplitude,
)


def _wav(samples: bytes, *, audio_format: int = 1, bits: int = 16) -> bytes:
    header = b"RIFF" + (36 + len(samples)).to_bytes(4, "little") + b"WAVEfmt "
    header += (16).to_bytes(4, "little") + audio_format.to_bytes(2, "little")
    header += (1).to_bytes(2, "little") + (16000).to_bytes(4, "little")
    header += (32000).to_bytes(4, "little") + ((bits // 8) * 1).to_bytes(2, "little")
    header += bits.to_bytes(2, "little") + b"data"
    header += len(samples).to_bytes(4, "little")
    return header + samples


def test_digital_silence_is_silent() -> None:
    data = _wav(b"\x00\x00" * 16000)
    assert wav_peak_amplitude(data) == 0
    assert is_silent_wav(data) is True


def test_low_floor_noise_is_still_silent() -> None:
    samples = struct.pack("<h", SILENCE_PEAK_FLOOR - 1) * 100
    assert is_silent_wav(_wav(samples)) is True


def test_a_spoken_word_is_not_silent() -> None:
    samples = struct.pack("<h", 1200) * 100
    assert wav_peak_amplitude(_wav(samples)) == 1200
    assert is_silent_wav(_wav(samples)) is False


def test_negative_samples_count_by_magnitude() -> None:
    samples = struct.pack("<h", -3000) + struct.pack("<h", 40) * 10
    assert wav_peak_amplitude(_wav(samples)) == 3000


def test_something_that_is_not_a_wav_is_not_judged() -> None:
    # m4a 是手机端最常见的形式；判断不了就交给上游，不要猜。
    assert wav_peak_amplitude(b"\x00\x01\x02" * 100) is None
    assert is_silent_wav(b"\x00\x01\x02" * 100) is False


def test_a_float_wav_is_not_judged() -> None:
    """浮点 WAV 的阈值口径不一样，宁可放弃判断也不误杀。"""

    assert wav_peak_amplitude(_wav(b"\x00" * 64, audio_format=3)) is None


def test_a_truncated_data_chunk_uses_what_arrived() -> None:
    """上传被截断时不该假装听得到，也不该崩。"""

    data = _wav(b"\x00\x00" * 8)
    truncated = data[:-2]
    assert wav_peak_amplitude(truncated) == 0
    assert is_silent_wav(truncated) is True


def test_an_odd_byte_count_does_not_raise() -> None:
    assert is_silent_wav(_wav(b"\x00\x00\x01")) is True


def test_a_wav_without_a_data_chunk_is_not_judged() -> None:
    header = b"RIFF" + (36).to_bytes(4, "little") + b"WAVEfmt "
    header += (16).to_bytes(4, "little") + (1).to_bytes(2, "little")
    header += (1).to_bytes(2, "little") + (16000).to_bytes(4, "little")
    header += (32000).to_bytes(4, "little") + (2).to_bytes(2, "little")
    header += (16).to_bytes(2, "little")
    assert wav_peak_amplitude(header) is None


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
