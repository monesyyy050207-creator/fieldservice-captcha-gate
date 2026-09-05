from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, EmailStr, Field, HttpUrl


class DispatchStatus(StrEnum):
    AWAITING_TRIAGE = "awaiting_triage"
    DISPATCHED = "dispatched"


class FollowUpStatus(StrEnum):
    NOT_SCHEDULED = "not_scheduled"
    SCHEDULED = "scheduled"


class WorkOrderPhoto(BaseModel):
    url: HttpUrl
    caption: str = Field(min_length=1, max_length=160)


class FieldServiceSignup(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12)
    name: str = Field(min_length=1, max_length=120)
    captcha_token: str = Field(min_length=1)
    widget_record_id: str = ""
    captcha_vendor: str = Field(min_length=1)
    requester_ip: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=8, max_length=128)
    work_order_summary: str = Field(min_length=1, max_length=500)
    photos: list[WorkOrderPhoto] = Field(default_factory=list, max_length=8)


class SignupResult(BaseModel):
    user_id: str
    work_order_summary: str
    photos: list[WorkOrderPhoto]
    dispatch_status: DispatchStatus
    technician_follow_up: FollowUpStatus


class SignupClient(Protocol):
    async def verify_captcha(self, **values: Any) -> dict[str, Any]:
        raise AssertionError("protocol method")

    async def create_user(self, **values: Any) -> dict[str, Any]:
        raise AssertionError("protocol method")


class SignupWorkflow:
    def __init__(self, client: SignupClient) -> None:
        self._client = client

    async def register(self, request: FieldServiceSignup) -> SignupResult:
        await self._client.verify_captcha(
            widget_record_id=request.widget_record_id,
            token=request.captcha_token,
            vendor=request.captcha_vendor,
            ip=request.requester_ip,
            action="field_service_signup",
            score_threshold=0.7,
        )
        metadata = {
            "work_order_summary": request.work_order_summary,
            "photos": [photo.model_dump(mode="json") for photo in request.photos],
            "dispatch_status": DispatchStatus.AWAITING_TRIAGE,
            "technician_follow_up": FollowUpStatus.NOT_SCHEDULED,
        }
        user = await self._client.create_user(
            email=str(request.email),
            password=request.password,
            name=request.name,
            metadata=metadata,
            vendor="infrai",
            mode="password",
            idempotency_key=request.idempotency_key,
        )
        return SignupResult(
            user_id=str(user["id"]),
            work_order_summary=request.work_order_summary,
            photos=request.photos,
            dispatch_status=DispatchStatus.AWAITING_TRIAGE,
            technician_follow_up=FollowUpStatus.NOT_SCHEDULED,
        )
