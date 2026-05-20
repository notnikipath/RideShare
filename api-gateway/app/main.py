from __future__ import annotations

from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.rideshare_common import BookTripWorkflowResult, QualityTargets, Role, Settings, sign_token, verify_token


class GatewaySettings(BaseSettings):
    service_name: str = "api-gateway"
    service_port: int = 8500

    trip_service_url: str = Settings().trip_service_url
    search_service_url: str = Settings().search_service_url
    booking_service_url: str = Settings().booking_service_url
    payment_service_url: str = Settings().payment_service_url
    rating_service_url: str = Settings().rating_service_url
    verification_service_url: str = Settings().verification_service_url
    chat_service_url: str = Settings().chat_service_url
    notification_service_url: str = Settings().notification_service_url

    jwt_secret: str = Settings().jwt_secret
    token_exp_minutes: int = 240

    search_target_seconds: float = Settings().search_target_seconds
    booking_target_seconds: float = Settings().booking_target_seconds
    daily_capacity_target: int = Settings().daily_capacity_target
    payment_commission_rate: float = Settings().payment_commission_rate

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = GatewaySettings()
app = FastAPI(title="RideShare API Gateway", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuthRequest(BaseModel):
    user_id: str
    role: Role
    language: str = Field(default="ru", pattern="^(ru|en)$")


class BookTripRequest(BaseModel):
    user_id: str
    trip_id: str
    seats: int = Field(gt=0, le=8)
    requires_baggage: bool = False
    with_pets: bool = False
    payment_async: bool = True


class CancelBookingWorkflowRequest(BaseModel):
    booking_id: str
    reason: str = "cancelled_by_user"
    user_id: str


class EmergencyWorkflowRequest(BaseModel):
    trip_id: str
    sender_id: str
    location: str
    details: str
    emergency_recipient: str = "+10000000000"


AuthRequest.model_rebuild()
BookTripRequest.model_rebuild()
CancelBookingWorkflowRequest.model_rebuild()
EmergencyWorkflowRequest.model_rebuild()


async def _post_json(client: httpx.AsyncClient, url: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = await client.post(url, json=payload)
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


async def _get_json(client: httpx.AsyncClient, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = await client.get(url, params=params)
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


def _service_urls() -> dict[str, str]:
    return {
        "trip": settings.trip_service_url,
        "search": settings.search_service_url,
        "booking": settings.booking_service_url,
        "payment": settings.payment_service_url,
        "rating": settings.rating_service_url,
        "verification": settings.verification_service_url,
        "chat": settings.chat_service_url,
        "notification": settings.notification_service_url,
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/auth/token")
async def issue_token(request: AuthRequest) -> dict[str, str]:
    token = sign_token(
        {"sub": request.user_id, "role": request.role.value, "language": request.language},
        settings.jwt_secret,
        exp_minutes=settings.token_exp_minutes,
    )
    return {"access_token": token, "token_type": "Bearer"}


@app.post("/auth/verify")
async def verify_auth(token: str) -> dict[str, Any]:
    payload = verify_token(token, settings.jwt_secret)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


@app.get("/services/health")
async def service_health() -> dict[str, Any]:
    statuses: dict[str, Any] = {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        for name, base_url in _service_urls().items():
            try:
                statuses[name] = await _get_json(client, f"{base_url}/health")
            except HTTPException as exc:
                statuses[name] = {"status": "error", "detail": exc.detail}
            except httpx.HTTPError as exc:
                statuses[name] = {"status": "error", "detail": str(exc)}
    return statuses


@app.post("/workflow/book-trip")
async def book_trip_workflow(request: BookTripRequest) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=25.0) as client:
        trip = await _get_json(client, f"{settings.trip_service_url}/trips/{request.trip_id}")
        if trip["available_seats"] < request.seats:
            raise HTTPException(status_code=409, detail="Not enough seats")
        if request.requires_baggage and not trip["allows_baggage"]:
            raise HTTPException(status_code=409, detail="Trip does not allow baggage")
        if request.with_pets and not trip["allows_pets"]:
            raise HTTPException(status_code=409, detail="Trip does not allow pets")

        booking = await _post_json(
            client,
            f"{settings.booking_service_url}/bookings",
            {
                "user_id": request.user_id,
                "trip_id": request.trip_id,
                "seats": request.seats,
                "unit_price": trip["price_per_seat"],
                "requires_baggage": request.requires_baggage,
                "with_pets": request.with_pets,
                "actor_id": "gateway",
                "actor_role": Role.SYSTEM.value,
            },
        )

        payment = await _post_json(
            client,
            f"{settings.payment_service_url}/payments/charge",
            {
                "booking_id": booking["booking_id"],
                "user_id": request.user_id,
                "amount": booking["subtotal_amount"],
                "commission_rate": settings.payment_commission_rate,
                "provider": "mockpay",
                "async_processing": request.payment_async,
                "actor_id": "gateway",
                "actor_role": Role.SYSTEM.value,
            },
        )

        if payment["status"] == "queued":
            await _post_json(client, f"{settings.payment_service_url}/payments/process-pending", {})
            payment = await _get_json(client, f"{settings.payment_service_url}/payments/{payment['payment_id']}")

        if payment["status"] != "succeeded":
            raise HTTPException(status_code=409, detail="Payment did not succeed")

        trip = await _post_json(
            client,
            f"{settings.trip_service_url}/trips/{request.trip_id}/seats/reserve",
            {
                "seats": request.seats,
                "booking_id": booking["booking_id"],
                "actor_id": "gateway",
                "actor_role": Role.SYSTEM.value,
            },
        )

        booking = await _post_json(
            client,
            f"{settings.booking_service_url}/bookings/{booking['booking_id']}/confirm-payment",
            {
                "payment_id": payment["payment_id"],
                "actor_id": "gateway",
                "actor_role": Role.SYSTEM.value,
            },
        )

        notification = await _post_json(
            client,
            f"{settings.notification_service_url}/notify/booking",
            {
                "driver_id": trip["driver_id"],
                "trip_id": request.trip_id,
                "booking_id": booking["booking_id"],
                "seats": request.seats,
                "actor_role": Role.SYSTEM.value,
            },
        )

        search_snapshot = await _get_json(
            client,
            f"{settings.search_service_url}/search/trips",
            {
                "origin": trip["origin"],
                "destination": trip["destination"],
                "departure_date": str(trip["departure_at"])[:10],
            },
        )
        search_sla = float(search_snapshot.get("search_time_estimate_seconds", settings.search_target_seconds))

        booking_latency = await _get_json(client, f"{settings.booking_service_url}/metrics/booking-latency")
        booking_sla = float(booking_latency.get("booking_time_estimate_seconds", settings.booking_target_seconds))

    result = BookTripWorkflowResult(
        trip=trip,
        booking=booking,
        payment=payment,
        notification=notification,
        search_sla_seconds=search_sla,
        booking_sla_seconds=booking_sla,
    )
    return result.model_dump(mode="json")


@app.post("/workflow/cancel-booking")
async def cancel_booking_workflow(request: CancelBookingWorkflowRequest) -> dict[str, Any]:
    refund = None
    async with httpx.AsyncClient(timeout=25.0) as client:
        booking = await _get_json(client, f"{settings.booking_service_url}/bookings/{request.booking_id}")

        booking = await _post_json(
            client,
            f"{settings.booking_service_url}/bookings/{request.booking_id}/cancel",
            {
                "reason": request.reason,
                "actor_id": request.user_id,
                "actor_role": Role.SYSTEM.value,
            },
        )

        if booking.get("payment_id"):
            refund = await _post_json(
                client,
                f"{settings.payment_service_url}/payments/{booking['payment_id']}/refund",
                {
                    "penalty_rate": 0.1,
                    "reason": request.reason,
                    "actor_id": request.user_id,
                    "actor_role": Role.SYSTEM.value,
                },
            )
            booking = await _post_json(
                client,
                f"{settings.booking_service_url}/bookings/{request.booking_id}/mark-refunded",
                {
                    "actor_id": "gateway",
                    "actor_role": Role.SYSTEM.value,
                },
            )

        trip = await _post_json(
            client,
            f"{settings.trip_service_url}/trips/{booking['trip_id']}/seats/release",
            {
                "seats": booking["seats"],
                "booking_id": booking["booking_id"],
                "actor_id": "gateway",
                "actor_role": Role.SYSTEM.value,
            },
        )

        notification = await _post_json(
            client,
            f"{settings.notification_service_url}/notify/cancellation",
            {
                "recipient": request.user_id,
                "trip_id": booking["trip_id"],
                "booking_id": booking["booking_id"],
                "reason": request.reason,
                "actor_role": Role.SYSTEM.value,
            },
        )

    return {
        "booking": booking,
        "trip": trip,
        "refund": refund,
        "notification": notification,
    }


@app.post("/workflow/emergency-assist")
async def emergency_workflow(request: EmergencyWorkflowRequest) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        chat_message = await _post_json(
            client,
            f"{settings.chat_service_url}/chat/{request.trip_id}/emergency",
            {
                "sender_id": request.sender_id,
                "location": request.location,
                "details": request.details,
                "actor_role": Role.PASSENGER.value,
            },
        )
        notification = await _post_json(
            client,
            f"{settings.notification_service_url}/notify/emergency",
            {
                "trip_id": request.trip_id,
                "recipient": request.emergency_recipient,
                "details": request.details,
                "actor_role": Role.SYSTEM.value,
            },
        )
    return {"chat": chat_message, "notification": notification}


@app.get("/quality/targets")
async def quality_targets() -> dict[str, Any]:
    targets = QualityTargets(
        search_seconds_target=settings.search_target_seconds,
        booking_seconds_target=settings.booking_target_seconds,
        trips_per_day_target=settings.daily_capacity_target,
    )

    async with httpx.AsyncClient(timeout=10.0) as client:
        booking_latency = await _get_json(client, f"{settings.booking_service_url}/metrics/booking-latency")
        cache = await _get_json(client, f"{settings.search_service_url}/search/cache/stats")

    return {
        "targets": targets.model_dump(mode="json"),
        "runtime": {
            "booking_estimate_seconds": booking_latency.get("booking_time_estimate_seconds"),
            "search_cache_hit_ratio": cache.get("hit_ratio"),
        },
    }


@app.get("/dashboard/{trip_id}/{user_id}")
async def dashboard(trip_id: str, user_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        trip = await _get_json(client, f"{settings.trip_service_url}/trips/{trip_id}")
        bookings = await _get_json(client, f"{settings.booking_service_url}/bookings", {"trip_id": trip_id})
        ratings = await _get_json(client, f"{settings.rating_service_url}/ratings/trip/{trip_id}")
        driver_profile = await _get_json(client, f"{settings.rating_service_url}/users/{trip['driver_id']}/profile")
        verification = await _get_json(client, f"{settings.verification_service_url}/verification/{user_id}")
        messages = await _get_json(client, f"{settings.chat_service_url}/chat/{trip_id}/messages")
        tracker = await _get_json(client, f"{settings.chat_service_url}/tracker/{trip_id}")
        notifications = await _get_json(
            client,
            f"{settings.notification_service_url}/notify/history",
            {"recipient": user_id},
        )
        search_cache = await _get_json(client, f"{settings.search_service_url}/search/cache/stats")
        fill_rate = await _get_json(client, f"{settings.trip_service_url}/metrics/fill-rate")

    return {
        "trip": trip,
        "bookings": bookings,
        "ratings": ratings,
        "driver_profile": driver_profile,
        "verification": verification,
        "chat": messages,
        "tracker": tracker,
        "notifications": notifications,
        "search_cache": search_cache,
        "fill_rate": fill_rate,
    }
