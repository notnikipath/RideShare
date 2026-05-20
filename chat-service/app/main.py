from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.rideshare_common import (
    ChatMessage,
    MessageType,
    Role,
    Settings,
    TrackerPoint,
    build_audit_event,
    has_permission,
)

settings = Settings(service_name="chat-service", service_port=8507)
app = FastAPI(title="RideShare Chat Service", version="1.0.0")

rooms: dict[str, list[ChatMessage]] = {"TRIP-DEMO-2": []}
trackers: dict[str, list[TrackerPoint]] = {"TRIP-DEMO-2": []}
audit_log: list[dict[str, Any]] = []


class SendMessageRequest(BaseModel):
    trip_id: str
    sender_id: str
    text: str = Field(min_length=1, max_length=2000)
    booking_id: str | None = None
    actor_role: Role


class EmergencyRequest(BaseModel):
    sender_id: str
    location: str
    details: str
    actor_role: Role


class TrackerPointRequest(BaseModel):
    trip_id: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    speed_kph: float = Field(ge=0, le=240)
    source: str = "driver_app"
    actor_role: Role


SendMessageRequest.model_rebuild()
EmergencyRequest.model_rebuild()
TrackerPointRequest.model_rebuild()


def _assert_permission(role: Role, action: str) -> None:
    if role == Role.ADMIN:
        return
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


def _audit(actor_id: str, actor_role: Role, action: str, object_id: str, details: dict[str, Any] | None = None) -> None:
    audit_log.append(
        build_audit_event(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            object_type="chat",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/chat/messages")
async def send_message(request: SendMessageRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "chat:send")
    message = ChatMessage(
        message_id=str(uuid4()),
        trip_id=request.trip_id,
        sender_id=request.sender_id,
        text=request.text,
        message_type=MessageType.CHAT,
        booking_id=request.booking_id,
    )
    rooms.setdefault(request.trip_id, []).append(message)
    _audit(request.sender_id, request.actor_role, "chat.message.send", message.message_id, {"trip_id": request.trip_id})
    return message.model_dump(mode="json")


@app.get("/chat/{trip_id}/messages")
async def get_messages(trip_id: str, limit: int = 50) -> dict[str, Any]:
    messages = rooms.get(trip_id, [])
    tail = messages[-max(limit, 1) :]
    return {"trip_id": trip_id, "items": [item.model_dump(mode="json") for item in tail], "count": len(tail)}


@app.post("/chat/{trip_id}/emergency")
async def emergency(trip_id: str, request: EmergencyRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "chat:send")
    text = f"EMERGENCY at {request.location}: {request.details}"
    message = ChatMessage(
        message_id=str(uuid4()),
        trip_id=trip_id,
        sender_id=request.sender_id,
        text=text,
        message_type=MessageType.EMERGENCY,
    )
    rooms.setdefault(trip_id, []).append(message)
    _audit(request.sender_id, request.actor_role, "chat.emergency", message.message_id, {"trip_id": trip_id})
    return {"status": "sent", "message": message.model_dump(mode="json")}


@app.post("/tracker/{trip_id}/points")
async def track_point(trip_id: str, request: TrackerPointRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "tracker:write")
    if trip_id != request.trip_id:
        raise HTTPException(status_code=400, detail="Path trip_id does not match payload")
    point = TrackerPoint(
        trip_id=request.trip_id,
        latitude=request.latitude,
        longitude=request.longitude,
        speed_kph=request.speed_kph,
        source=request.source,
        timestamp=datetime.now(UTC),
    )
    trackers.setdefault(trip_id, []).append(point)
    _audit("tracker", request.actor_role, "tracker.point", trip_id)
    return {"accepted": True, "trip_id": trip_id, "points": len(trackers.get(trip_id, []))}


@app.get("/tracker/{trip_id}")
async def tracker_history(trip_id: str, limit: int = 100) -> dict[str, Any]:
    points = trackers.get(trip_id, [])
    tail = points[-max(limit, 1) :]
    return {"trip_id": trip_id, "items": [point.model_dump(mode="json") for point in tail], "count": len(tail)}


@app.get("/tracker/{trip_id}/latest")
async def latest_point(trip_id: str) -> dict[str, Any]:
    points = trackers.get(trip_id, [])
    if not points:
        raise HTTPException(status_code=404, detail="No tracker points for trip")
    return points[-1].model_dump(mode="json")


@app.get("/chat/rooms")
async def chat_rooms() -> dict[str, Any]:
    items = []
    for trip_id, messages in rooms.items():
        items.append(
            {
                "trip_id": trip_id,
                "messages": len(messages),
                "last_message_at": messages[-1].created_at if messages else None,
            }
        )
    return {"items": items, "count": len(items)}


@app.get("/audit")
async def get_audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}
