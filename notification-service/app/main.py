from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from shared.rideshare_common import NotificationChannel, Role, Settings, Severity, has_permission

settings = Settings(service_name="notification-service", service_port=8508)
app = FastAPI(title="RideShare Notification Service", version="1.0.0")

messages: list[dict[str, Any]] = []


class NotificationRequest(BaseModel):
    channel: NotificationChannel
    recipient: str
    subject: str
    body: str
    severity: Severity = Severity.INFO
    actor_role: Role


class BookingNotificationRequest(BaseModel):
    driver_id: str
    trip_id: str
    booking_id: str
    seats: int
    actor_role: Role


class CancellationNotificationRequest(BaseModel):
    recipient: str
    trip_id: str
    booking_id: str
    reason: str
    actor_role: Role


class EmergencyNotificationRequest(BaseModel):
    trip_id: str
    recipient: str
    details: str
    actor_role: Role


NotificationRequest.model_rebuild()
BookingNotificationRequest.model_rebuild()
CancellationNotificationRequest.model_rebuild()
EmergencyNotificationRequest.model_rebuild()


def _assert_permission(role: Role, action: str) -> None:
    if role == Role.ADMIN:
        return
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


def _append(payload: dict[str, Any]) -> dict[str, Any]:
    payload["created_at"] = datetime.now(UTC).isoformat()
    payload["status"] = "queued"
    messages.append(payload)
    return payload


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/notify/send")
async def send_notification(request: NotificationRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "notification:send")
    return _append(request.model_dump(mode="json"))


@app.post("/notify/booking")
async def notify_booking(request: BookingNotificationRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "notification:send")
    payload = {
        "channel": NotificationChannel.PUSH.value,
        "recipient": request.driver_id,
        "subject": f"New booking for {request.trip_id}",
        "body": f"Booking {request.booking_id}: {request.seats} seat(s) reserved.",
        "severity": Severity.INFO.value,
    }
    return _append(payload)


@app.post("/notify/cancellation")
async def notify_cancellation(request: CancellationNotificationRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "notification:send")
    payload = {
        "channel": NotificationChannel.IN_APP.value,
        "recipient": request.recipient,
        "subject": f"Booking cancelled: {request.booking_id}",
        "body": f"Trip {request.trip_id} cancellation reason: {request.reason}",
        "severity": Severity.WARNING.value,
    }
    return _append(payload)


@app.post("/notify/emergency")
async def notify_emergency(request: EmergencyNotificationRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "notification:send")
    payload = {
        "channel": NotificationChannel.SMS.value,
        "recipient": request.recipient,
        "subject": f"Emergency alert on trip {request.trip_id}",
        "body": request.details,
        "severity": Severity.CRITICAL.value,
    }
    return _append(payload)


@app.get("/notify/history")
async def history(recipient: str | None = None) -> dict[str, Any]:
    if recipient:
        items = [item for item in messages if item["recipient"] == recipient]
    else:
        items = messages
    return {"items": items, "count": len(items)}
