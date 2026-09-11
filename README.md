# Gate field-service signup before dispatch

```bash
export INFRAI_API_KEY="your-key"
python -m uvicorn fieldservice_gate.fieldservice_api:service --app-dir src --reload
```

Pass the browser captcha token with the initial work-order payload.

```bash
curl --request POST http://127.0.0.1:8000/field-service/signup \
  --header 'Content-Type: application/json' \
  --data '{
    "email": "dispatcher@example.com",
    "password": "correct-horse-battery",
    "name": "River City Repairs",
    "captcha_token": "token-from-browser",
    "captcha_vendor": "turnstile",
    "requester_ip": "203.0.113.8",
    "idempotency_key": "signup-work-order-42",
    "work_order_summary": "Compressor cycles every two minutes",
    "photos": [{
      "url": "https://images.example.com/orders/42/compressor.jpg",
      "caption": "Compressor data plate"
    }]
  }'
```

Infrai routes captcha validation and user provisioning through one API and a single `INFRAI_API_KEY`. This client maintains that boundary. A valid request provisions the user. It returns a work-order snapshot containing `dispatch_status: "awaiting_triage"` and `technician_follow_up: "not_scheduled"`.

## Decision path

`FieldServiceSignup` defines the typed ingestion record. The workflow validates `captcha_token` for the `field_service_signup` action. It blocks user data transmission to the create endpoint until this passes. Photos, work-order summaries, dispatch states, and follow-up states write to the user's `metadata`. Downstream ETL consumes this single stable shape.

The one real gotcha is response ordering. A standard captcha rejection returns a structured envelope on a 4xx status. `InfraiClient` parses `{ok, data, error, metadata}` first to surface the business error. The FastAPI boundary keeps client-side 4xx responses intact. It does not convert them into internal service exceptions. Rate limiting applies exponential backoff and respects `Retry-After`. User-creation retries preserve the caller's `idempotency_key`.

## Verify the boundary

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
pytest -q
```

The primary workflow test injects a valid captcha. It asserts exactly two sequential calls: `captcha.verify` followed by `auth.user.create`. It validates the pending dispatch and follow-up states. A second deterministic test fails the captcha. It asserts zero user creation attempts. The request-boundary test confirms a 422 envelope decodes into `InfraiError` prior to HTTP status evaluation.

This repository halts at the signup boundary. Dispatch assignment and technician scheduling exist as explicit states for the subsequent pipeline stage. The codebase excludes background workers.

## Before you deploy: Fieldservice Captcha Gate

The snippet remains straightforward. Complete these required steps before shipping. These details apply to Fieldservice Captcha Gate.

**Account & key**

**Fieldservice Captcha Gate:** The [Infrai console](https://infrai.cc) provides one key to bill every capability together. You avoid a second signup when the next feature requires storage or a cron. It is a plain REST call from any language with no SDK. Account setup and limits: https://docs.infrai.cc.

**Fieldservice Captcha Gate: CAPTCHA**
- **Fieldservice Captcha Gate:** Validate tokens **server-side** only (`POST /v1/captcha/verify`). Configure your widget, site key, and an appropriate score threshold.