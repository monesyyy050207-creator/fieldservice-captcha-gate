import httpx
import pytest

from fieldservice_gate.infrai_client import InfraiClient, InfraiError


@pytest.mark.asyncio
async def test_business_envelope_is_read_before_http_status() -> None:
    async def reject(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        return httpx.Response(
            422,
            json={
                "ok": False,
                "data": None,
                "error": {
                    "code": "CAPTCHA_SCORE_TOO_LOW",
                    "message": "Captcha score is below threshold",
                },
                "metadata": {},
            },
        )

    client = InfraiClient("test-key", transport=httpx.MockTransport(reject))
    try:
        with pytest.raises(InfraiError) as captured:
            await client.verify_captcha(
                token="browser-token",
                vendor="turnstile",
                ip="203.0.113.8",
                action="field_service_signup",
                score_threshold=0.7,
            )
        assert captured.value.status_code == 422
    finally:
        await client.close()
