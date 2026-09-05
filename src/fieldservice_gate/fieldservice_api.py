import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException

from .infrai_client import InfraiClient, InfraiError
from .signup_workflow import FieldServiceSignup, SignupResult, SignupWorkflow


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    api_key = os.environ["INFRAI_API_KEY"]
    client = InfraiClient(api_key)
    app.state.workflow = SignupWorkflow(client)
    yield
    await client.close()


service = FastAPI(title="Field-service signup gate", lifespan=lifespan)


@service.post("/field-service/signup", response_model=SignupResult, status_code=201)
async def signup(request: FieldServiceSignup) -> SignupResult:
    try:
        return await service.state.workflow.register(request)
    except InfraiError as exc:
        status_code = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=status_code,
            detail={"code": exc.code, "message": exc.detail.get("message", "Request rejected")},
        ) from exc

