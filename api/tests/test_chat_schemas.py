from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from antang_api.schemas.chat import SendMessageRequest

MEASURED_AT = datetime(2026, 7, 26, 22, 0, tzinfo=timezone.utc)


def reading(**overrides: object) -> dict[str, Any]:
    """构造一份合法的实时心率读数。"""

    payload: dict[str, Any] = {
        "beats_per_minute": 89,
        "measured_at": MEASURED_AT.isoformat(),
        "device_name": "HUAWEI Band 9-598",
    }
    payload.update(overrides)
    return payload


def body(**overrides: object) -> dict[str, Any]:
    """构造一份发消息请求体，与手机实际提交的 JSON 一致。"""

    payload: dict[str, Any] = {
        "client_message_id": str(uuid4()),
        "content": "我有点心慌",
    }
    payload.update(overrides)
    return payload


def test_send_message_request_accepts_a_live_heart_rate_reading() -> None:
    request = SendMessageRequest.model_validate(body(live_heart_rate=reading()))

    assert request.live_heart_rate is not None
    assert request.live_heart_rate.beats_per_minute == 89
    assert request.live_heart_rate.measured_at == MEASURED_AT
    assert request.live_heart_rate.device_name == "HUAWEI Band 9-598"


def test_send_message_request_stays_valid_without_a_live_heart_rate() -> None:
    request = SendMessageRequest.model_validate(body())

    assert request.live_heart_rate is None


@pytest.mark.parametrize("beats_per_minute", [10, 400])
def test_send_message_request_rejects_out_of_range_heart_rates(
    beats_per_minute: int,
) -> None:
    with pytest.raises(ValidationError):
        SendMessageRequest.model_validate(
            body(live_heart_rate=reading(beats_per_minute=beats_per_minute))
        )


def test_send_message_request_rejects_extra_reading_fields() -> None:
    with pytest.raises(ValidationError):
        SendMessageRequest.model_validate(
            body(live_heart_rate=reading(rr_intervals=[900]))
        )
