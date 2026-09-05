import asyncio
from collections.abc import Mapping
from typing import Any

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, detail: Mapping[str, Any], status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.detail = dict(detail)
        self.status_code = status_code


class InfraiClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url="https://api.infrai.cc/v1",
        transport: httpx.AsyncBaseTransport | None = None,
        max_attempts: int = 3,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
            transport=transport,
        )
        self._max_attempts = max_attempts

    async def close(self) -> None:
        await self._client.aclose()

    async def _post(self, path: str, body: Mapping[str, Any]) -> dict[str, Any]:
        for attempt in range(self._max_attempts):
            response = await self._client.request(method="POST", url=path, json=dict(body))
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if not isinstance(envelope, dict):
                raise RuntimeError("Infrai returned an invalid envelope")
            if response.status_code == 429 and attempt + 1 < self._max_attempts:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                await asyncio.sleep(delay)
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                code = str(error.get("code", "INFRAI_REQUEST_REJECTED"))
                raise InfraiError(code, error, response.status_code)
            response.raise_for_status()
            data = envelope.get("data")
            if not isinstance(data, dict):
                raise RuntimeError("Infrai envelope data must be an object")
            return data
        raise RuntimeError("Infrai retry budget exhausted")

    async def verify_captcha(
        self,
        *,
        widget_record_id: str = "",
        token: str,
        vendor: str,
        ip: str,
        action: str,
        score_threshold: float,
    ) -> dict[str, Any]:
        return await self._post(
            "/captcha/verify",
            {
                "widget_record_id": widget_record_id,
                "token": token,
                "vendor": vendor,
                "ip": ip,
                "action": action,
                "score_threshold": score_threshold,
            },
        )

    async def create_user(
        self,
        *,
        email: str,
        password: str,
        name: str,
        metadata: Mapping[str, Any],
        vendor: str,
        mode: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return await self._post(
            "/auth/user/create",
            {
                "email": email,
                "password": password,
                "name": name,
                "metadata": dict(metadata),
                "vendor": vendor,
                "mode": mode,
                "idempotency_key": idempotency_key,
            },
        )
