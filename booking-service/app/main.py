from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from shared.rideshare_common import (
    BookingCreateRequest,
    BookingRecord,
    BookingStatus,
    Role,
    Settings,
    build_audit_event,
    estimate_booking_seconds,
    has_permission,
)

settings = Settings(service_name="booking-service", service_port=8503)
app = FastAPI(title="RideShare Booking Service", version="1.0.0")

bookings: dict[str, BookingRecord] = {}
audit_log: list[dict[str, Any]] = []


class ConfirmPaymentRequest(BaseModel):
    payment_id: str
    actor_id: str
    actor_role: Role


class CancelBookingRequest(BaseModel):
    reason: str = "cancelled_by_user"
    actor_id: str
    actor_role: Role


class MarkRefundedRequest(BaseModel):
    actor_id: str
    actor_role: Role


ConfirmPaymentRequest.model_rebuild()
CancelBookingRequest.model_rebuild()
MarkRefundedRequest.model_rebuild()


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
            object_type="booking",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


def _seed_demo() -> None:
    booking = BookingRecord(
        booking_id="BOOK-DEMO-1",
        user_id="USR-301",
        trip_id="TRIP-DEMO-2",
        seats=1,
        unit_price=420,
        subtotal_amount=420,
        commission_amount=42,
        total_amount=462,
        status=BookingStatus.CONFIRMED,
        requires_baggage=True,
        with_pets=False,
        payment_id="PAY-DEMO-1",
    )
    bookings[booking.booking_id] = booking


_seed_demo()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/bookings")
async def list_bookings(
    user_id: str | None = None,
    trip_id: str | None = None,
    status: BookingStatus | None = None,
) -> dict[str, Any]:
    items = []
    for booking in bookings.values():
        if user_id and booking.user_id != user_id:
            continue
        if trip_id and booking.trip_id != trip_id:
            continue
        if status and booking.status != status:
            continue
        items.append(booking.model_dump(mode="json"))
    items.sort(key=lambda item: item["created_at"], reverse=True)
    return {"items": items, "count": len(items)}


@app.get("/bookings/{booking_id}")
async def get_booking(booking_id: str) -> dict[str, Any]:
    booking = bookings.get(booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking.model_dump(mode="json")


@app.post("/bookings")
async def create_booking(request: BookingCreateRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "booking:create")
    subtotal = round(request.unit_price * request.seats, 2)
    commission = round(subtotal * settings.payment_commission_rate, 2)
    booking = BookingRecord(
        booking_id=str(uuid4()),
        user_id=request.user_id,
        trip_id=request.trip_id,
        seats=request.seats,
        unit_price=request.unit_price,
        subtotal_amount=subtotal,
        commission_amount=commission,
        total_amount=round(subtotal + commission, 2),
        requires_baggage=request.requires_baggage,
        with_pets=request.with_pets,
    )
    bookings[booking.booking_id] = booking
    _audit(request.actor_id, request.actor_role, "booking.create", booking.booking_id, {"trip_id": request.trip_id})
    return booking.model_dump(mode="json")


@app.post("/bookings/{booking_id}/confirm-payment")
async def confirm_payment(booking_id: str, request: ConfirmPaymentRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "booking:create")
    booking = bookings.get(booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.status not in {BookingStatus.PENDING_PAYMENT, BookingStatus.CONFIRMED}:
        raise HTTPException(status_code=409, detail=f"Cannot confirm booking in status {booking.status.value}")
    booking.status = BookingStatus.CONFIRMED
    booking.payment_id = request.payment_id
    booking.updated_at = datetime.now(UTC)
    _audit(
        request.actor_id,
        request.actor_role,
        "booking.confirm_payment",
        booking_id,
        {"payment_id": request.payment_id},
    )
    return booking.model_dump(mode="json")


@app.post("/bookings/{booking_id}/cancel")
async def cancel_booking(booking_id: str, request: CancelBookingRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "booking:cancel")
    booking = bookings.get(booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.status in {BookingStatus.CANCELLED, BookingStatus.REFUNDED}:
        return booking.model_dump(mode="json")
    booking.status = BookingStatus.CANCELLED
    booking.cancellation_reason = request.reason
    booking.updated_at = datetime.now(UTC)
    _audit(request.actor_id, request.actor_role, "booking.cancel", booking_id, {"reason": request.reason})
    return booking.model_dump(mode="json")


@app.post("/bookings/{booking_id}/mark-refunded")
async def mark_refunded(booking_id: str, request: MarkRefundedRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "booking:cancel")
    booking = bookings.get(booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    booking.status = BookingStatus.REFUNDED
    booking.updated_at = datetime.now(UTC)
    _audit(request.actor_id, request.actor_role, "booking.refund_mark", booking_id)
    return booking.model_dump(mode="json")


@app.get("/bookings/trip/{trip_id}/passengers")
async def trip_passengers(trip_id: str) -> dict[str, Any]:
    items = [
        {
            "booking_id": booking.booking_id,
            "user_id": booking.user_id,
            "seats": booking.seats,
            "status": booking.status,
        }
        for booking in bookings.values()
        if booking.trip_id == trip_id
    ]
    return {"trip_id": trip_id, "items": items, "count": len(items)}


@app.get("/metrics/booking-latency")
async def booking_latency(queue_depth: int = 120, async_payment: bool = True) -> dict[str, Any]:
    estimate = estimate_booking_seconds(queue_depth, async_payment)
    return {
        "booking_time_estimate_seconds": estimate,
        "sla_seconds": settings.booking_target_seconds,
        "sla_ok": estimate < settings.booking_target_seconds,
    }


@app.get("/audit")
async def get_audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}
