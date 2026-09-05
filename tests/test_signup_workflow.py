from typing import Any

import pytest

from fieldservice_gate.infrai_client import InfraiError
from fieldservice_gate.signup_workflow import FieldServiceSignup, SignupWorkflow


class RecordingClient:
    def __init__(self, captcha_error: InfraiError | None = None) -> None:
        self.captcha_error = captcha_error
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def verify_captcha(self, **values: Any) -> dict[str, Any]:
        self.calls.append(("captcha.verify", values))
        if self.captcha_error:
            raise self.captcha_error
        return {"verified": True}

    async def create_user(self, **values: Any) -> dict[str, Any]:
        self.calls.append(("auth.user.create", values))
        return {"id": "usr_field_42"}


def signup_request() -> FieldServiceSignup:
    return FieldServiceSignup(
        email="dispatcher@example.com",
        password="correct-horse-battery",
        name="River City Repairs",
        captcha_token="browser-token",
        captcha_vendor="turnstile",
        requester_ip="203.0.113.8",
        idempotency_key="signup-work-order-42",
        work_order_summary="Compressor cycles every two minutes",
        photos=[
            {
                "url": "https://images.example.com/orders/42/compressor.jpg",
                "caption": "Compressor data plate",
            }
        ],
    )


@pytest.mark.asyncio
async def test_verified_signup_creates_user_and_pending_dispatch() -> None:
    client = RecordingClient()
    result = await SignupWorkflow(client).register(signup_request())

    assert [name for name, _ in client.calls] == ["captcha.verify", "auth.user.create"]
    assert client.calls[1][1]["idempotency_key"] == "signup-work-order-42"
    assert result.user_id == "usr_field_42"
    assert result.dispatch_status == "awaiting_triage"
    assert result.technician_follow_up == "not_scheduled"


@pytest.mark.asyncio
async def test_rejected_captcha_stops_before_user_creation() -> None:
    rejection = InfraiError(
        "CAPTCHA_SCORE_TOO_LOW", {"message": "Captcha score is below threshold"}, 422
    )
    client = RecordingClient(rejection)

    with pytest.raises(InfraiError):
        await SignupWorkflow(client).register(signup_request())

    assert [name for name, _ in client.calls] == ["captcha.verify"]
