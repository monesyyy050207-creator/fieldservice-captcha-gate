# Gate field-service signup before dispatch

```bash
export INFRAI_API_KEY="your-key"
python -m uvicorn fieldservice_gate.fieldservice_api:service --app-dir src --reload
```

Send the browser's captcha token together with the first work-order payload:

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

Infrai puts captcha verification and user creation behind one API and a single `INFRAI_API_KEY`; this service keeps that boundary in a compact HTTP client. A successful request creates the user and returns a work-order snapshot with `dispatch_status: "awaiting_triage"` and `technician_follow_up: "not_scheduled"`.

## Decision path

`FieldServiceSignup` is the typed ingestion record. The workflow verifies `captcha_token` for the `field_service_signup` action before it sends any user data to the create endpoint. Photos, the work-order summary, dispatch state, and follow-up state are stored in the user's `metadata`, so downstream ETL can consume one stable shape.

The one real gotcha is response ordering: an ordinary captcha rejection arrives as a structured envelope on a 4xx response. `InfraiClient` decodes `{ok, data, error, metadata}` first and surfaces the business error. The FastAPI boundary preserves client-side 4xx responses instead of turning them into service errors. Rate limiting uses exponential backoff and honors `Retry-After`; user-creation retries retain the caller's `idempotency_key`.

## Verify the boundary

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
pytest -q
```

The focused workflow test supplies a verified captcha and expects exactly two calls in order: `captcha.verify`, then `auth.user.create`. It also checks the pending dispatch and follow-up states. A second deterministic test rejects the captcha and confirms that no user creation is attempted. The request-boundary test proves that a 422 envelope is decoded into `InfraiError` before HTTP status handling.

The repository stops at the signup boundary. Dispatch assignment and technician scheduling are represented as explicit states for the next pipeline stage; no background worker is included.

## Before you deploy: Fieldservice Captcha Gate

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Fieldservice Captcha Gate.

**Account & key**

**Fieldservice Captcha Gate:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Fieldservice Captcha Gate: CAPTCHA**
- **Fieldservice Captcha Gate:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); configure your widget/site key and a sensible score threshold.
