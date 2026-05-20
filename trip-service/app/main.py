from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.rideshare_common import (
    Role,
    SeatMutationRequest,
    Settings,
    Trip,
    TripCreateRequest,
    TripStatus,
    TripType,
    build_audit_event,
    dynamic_price,
    fill_rate,
    forecast_fill_rate,
    has_permission,
)

settings = Settings(service_name="trip-service", service_port=8501)
app = FastAPI(title="RideShare Trip Service", version="1.0.0")

trips: dict[str, Trip] = {}
trip_booking_refs: dict[str, list[str]] = {}
audit_log: list[dict[str, Any]] = []


class ForecastRequest(BaseModel):
    trend_score: float = Field(default=0.5, ge=0, le=1)


class DynamicPriceRequest(BaseModel):
    demand_ratio: float = Field(default=0.4, ge=0, le=1)
    hours_to_departure: float | None = Field(default=None, ge=0)


ForecastRequest.model_rebuild()
DynamicPriceRequest.model_rebuild()


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
            object_type="trip",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


def _apply_status(trip: Trip) -> None:
    if trip.status in {TripStatus.CANCELLED, TripStatus.COMPLETED}:
        return
    trip.status = TripStatus.FULL if trip.available_seats <= 0 else TripStatus.OPEN


def _seed_demo() -> None:
    now = datetime.now(UTC)
    seeded = [
        Trip(
            trip_id="TRIP-DEMO-1",
            driver_id="DRV-100",
            trip_type=TripType.INTERCITY,
            origin="Moscow",
            destination="Tver",
            departure_at=now + timedelta(hours=18),
            total_seats=3,
            available_seats=3,
            price_per_seat=1350,
            allows_baggage=True,
            allows_pets=False,
        ),
        Trip(
            trip_id="TRIP-DEMO-2",
            driver_id="DRV-221",
            trip_type=TripType.SUBURBAN,
            origin="Moscow",
            destination="Zelenograd",
            departure_at=now + timedelta(hours=6),
            total_seats=2,
            available_seats=1,
            price_per_seat=420,
            allows_baggage=True,
            allows_pets=True,
        ),
        Trip(
            trip_id="TRIP-DEMO-3",
            driver_id="DRV-350",
            trip_type=TripType.CARPOOL,
            origin="Khimki",
            destination="Moscow",
            departure_at=now + timedelta(hours=10),
            total_seats=4,
            available_seats=4,
            price_per_seat=280,
            allows_baggage=False,
            allows_pets=False,
            is_recurring=True,
            recurring_days=[1, 2, 3, 4, 5],
        ),
    ]
    for item in seeded:
        trips[item.trip_id] = item
        trip_booking_refs[item.trip_id] = []


_seed_demo()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/trips")
async def list_trips(
    origin: str | None = None,
    destination: str | None = None,
    departure_date: str | None = None,
    trip_type: TripType | None = None,
    requires_baggage: bool | None = None,
    with_pets: bool | None = None,
    only_available: bool = True,
) -> dict[str, Any]:
    items = []
    for trip in trips.values():
        if origin and origin.casefold() not in trip.origin.casefold():
            continue
        if destination and destination.casefold() not in trip.destination.casefold():
            continue
        if departure_date and str(trip.departure_at.date()) != departure_date:
            continue
        if trip_type and trip.trip_type != trip_type:
            continue
        if requires_baggage is True and not trip.allows_baggage:
            continue
        if with_pets is True and not trip.allows_pets:
            continue
        if only_available and trip.available_seats <= 0:
            continue
        items.append(trip.model_dump(mode="json"))
    items.sort(key=lambda item: item["departure_at"])
    return {"items": items, "count": len(items)}


@app.get("/trips/{trip_id}")
async def get_trip(trip_id: str) -> dict[str, Any]:
    trip = trips.get(trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip.model_dump(mode="json")


@app.post("/trips")
async def create_trip(request: TripCreateRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "trip:create")
    trip = Trip(
        trip_id=str(uuid4()),
        driver_id=request.driver_id,
        trip_type=request.trip_type,
        origin=request.origin,
        destination=request.destination,
        departure_at=request.departure_at,
        total_seats=request.total_seats,
        available_seats=request.total_seats,
        price_per_seat=request.price_per_seat,
        allows_baggage=request.allows_baggage,
        allows_pets=request.allows_pets,
        is_recurring=request.is_recurring,
        recurring_days=request.recurring_days,
    )
    trips[trip.trip_id] = trip
    trip_booking_refs[trip.trip_id] = []
    _audit(request.actor_id, request.actor_role, "trip.create", trip.trip_id)
    return trip.model_dump(mode="json")


@app.post("/trips/{trip_id}/seats/reserve")
async def reserve_seats(trip_id: str, request: SeatMutationRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "trip:update")
    trip = trips.get(trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    if trip.status in {TripStatus.CANCELLED, TripStatus.COMPLETED}:
        raise HTTPException(status_code=409, detail=f"Trip status is {trip.status.value}")
    if trip.available_seats < request.seats:
        raise HTTPException(status_code=409, detail="Not enough seats")

    trip.available_seats -= request.seats
    _apply_status(trip)
    if request.booking_id:
        refs = trip_booking_refs.setdefault(trip_id, [])
        if request.booking_id not in refs:
            refs.append(request.booking_id)

    _audit(
        request.actor_id,
        request.actor_role,
        "trip.seats.reserve",
        trip_id,
        {"seats": request.seats, "booking_id": request.booking_id},
    )
    return trip.model_dump(mode="json")


@app.post("/trips/{trip_id}/seats/release")
async def release_seats(trip_id: str, request: SeatMutationRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "trip:update")
    trip = trips.get(trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    trip.available_seats = min(trip.total_seats, trip.available_seats + request.seats)
    _apply_status(trip)
    _audit(
        request.actor_id,
        request.actor_role,
        "trip.seats.release",
        trip_id,
        {"seats": request.seats, "booking_id": request.booking_id},
    )
    return trip.model_dump(mode="json")


@app.get("/trips/{trip_id}/bookings")
async def get_trip_bookings(trip_id: str) -> dict[str, Any]:
    if trip_id not in trips:
        raise HTTPException(status_code=404, detail="Trip not found")
    refs = trip_booking_refs.get(trip_id, [])
    return {"trip_id": trip_id, "booking_ids": refs, "count": len(refs)}


@app.get("/drivers/{driver_id}/trips")
async def get_driver_trips(driver_id: str) -> dict[str, Any]:
    items = [trip.model_dump(mode="json") for trip in trips.values() if trip.driver_id == driver_id]
    items.sort(key=lambda item: item["departure_at"])
    return {"driver_id": driver_id, "items": items, "count": len(items)}


@app.post("/trips/{trip_id}/price-preview")
async def price_preview(trip_id: str, request: DynamicPriceRequest) -> dict[str, Any]:
    trip = trips.get(trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    hours_to_departure = request.hours_to_departure
    if hours_to_departure is None:
        delta = trip.departure_at - datetime.now(UTC)
        hours_to_departure = max(delta.total_seconds() / 3600, 0)
    suggested = dynamic_price(trip.price_per_seat, request.demand_ratio, hours_to_departure)
    return {
        "trip_id": trip_id,
        "base_price": trip.price_per_seat,
        "demand_ratio": request.demand_ratio,
        "hours_to_departure": round(hours_to_departure, 2),
        "suggested_price": suggested,
    }


@app.post("/trips/{trip_id}/occupancy-forecast")
async def occupancy_forecast(trip_id: str, request: ForecastRequest) -> dict[str, Any]:
    trip = trips.get(trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    current_fill = fill_rate(trip.total_seats, trip.available_seats)
    days_to_departure = max((trip.departure_at.date() - datetime.now(UTC).date()).days, 0)
    projected = forecast_fill_rate(current_fill, days_to_departure, request.trend_score)
    return {
        "trip_id": trip_id,
        "current_fill_rate": current_fill,
        "projected_fill_rate": projected,
        "days_to_departure": days_to_departure,
    }


@app.get("/metrics/fill-rate")
async def fill_rate_metrics() -> dict[str, Any]:
    if not trips:
        return {"avg_fill_rate": 0.0, "open_trips": 0}
    values = [fill_rate(trip.total_seats, trip.available_seats) for trip in trips.values()]
    avg_fill_rate = round(sum(values) / len(values), 3)
    open_trips = len([trip for trip in trips.values() if trip.status == TripStatus.OPEN])
    return {"avg_fill_rate": avg_fill_rate, "open_trips": open_trips, "total_trips": len(trips)}


@app.get("/audit")
async def get_audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}
