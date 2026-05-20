from __future__ import annotations

from datetime import UTC, datetime, timedelta
from math import sqrt
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.rideshare_common import (
    Role,
    Settings,
    Trip,
    TripType,
    TTLCache,
    companion_score,
    estimate_search_seconds,
    has_permission,
    search_parallel_plan,
)

settings = Settings(service_name="search-service", service_port=8502)
app = FastAPI(title="RideShare Search Service", version="1.0.0")

city_coords: dict[str, tuple[float, float]] = {
    "Moscow": (55.7558, 37.6173),
    "Tver": (56.8587, 35.9176),
    "Khimki": (55.897, 37.4297),
    "Zelenograd": (55.9825, 37.1815),
    "Odintsovo": (55.678, 37.2777),
    "Mytishchi": (55.9095, 37.7333),
}

indexed_trips: dict[str, dict[str, Any]] = {}
geo_cache = TTLCache(ttl_seconds=900)
cache_hits = 0
cache_misses = 0


class IndexSyncRequest(BaseModel):
    trips: list[Trip]
    actor_id: str
    actor_role: Role


class RecommendationRequest(BaseModel):
    user_id: str
    origin: str
    destination: str
    passenger_rating: float = Field(default=4.7, ge=0, le=5)
    requires_baggage: bool = False
    with_pets: bool = False


IndexSyncRequest.model_rebuild()
RecommendationRequest.model_rebuild()


def _assert_permission(role: Role, action: str) -> None:
    if role == Role.ADMIN:
        return
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


def _seed() -> None:
    now = datetime.now(UTC)
    seeded: list[dict[str, Any]] = [
        {
            "trip_id": "TRIP-DEMO-1",
            "driver_id": "DRV-100",
            "trip_type": TripType.INTERCITY.value,
            "origin": "Moscow",
            "destination": "Tver",
            "departure_at": (now + timedelta(hours=18)).isoformat(),
            "available_seats": 3,
            "price_per_seat": 1350,
            "allows_baggage": True,
            "allows_pets": False,
            "driver_rating": 4.9,
            "historical_fill": 0.74,
        },
        {
            "trip_id": "TRIP-DEMO-2",
            "driver_id": "DRV-221",
            "trip_type": TripType.SUBURBAN.value,
            "origin": "Moscow",
            "destination": "Zelenograd",
            "departure_at": (now + timedelta(hours=6)).isoformat(),
            "available_seats": 1,
            "price_per_seat": 420,
            "allows_baggage": True,
            "allows_pets": True,
            "driver_rating": 4.4,
            "historical_fill": 0.88,
        },
        {
            "trip_id": "TRIP-DEMO-3",
            "driver_id": "DRV-350",
            "trip_type": TripType.CARPOOL.value,
            "origin": "Khimki",
            "destination": "Moscow",
            "departure_at": (now + timedelta(hours=10)).isoformat(),
            "available_seats": 4,
            "price_per_seat": 280,
            "allows_baggage": False,
            "allows_pets": False,
            "driver_rating": 4.7,
            "historical_fill": 0.63,
        },
    ]
    for item in seeded:
        indexed_trips[item["trip_id"]] = item


_seed()


def _coords(city: str) -> tuple[float, float] | None:
    global cache_hits
    global cache_misses

    cache_key = f"geo:{city.casefold()}"
    cached = geo_cache.get(cache_key)
    if isinstance(cached, tuple):
        cache_hits += 1
        return cached

    cache_misses += 1
    point = city_coords.get(city)
    if point is not None:
        geo_cache.set(cache_key, point)
    return point


def _route_distance_km(origin: str, destination: str) -> float:
    start = _coords(origin)
    end = _coords(destination)
    if start is None or end is None:
        return 0.0
    dlat = start[0] - end[0]
    dlon = start[1] - end[1]
    return round(sqrt(dlat * dlat + dlon * dlon) * 111, 1)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/search/trips")
async def search_trips(
    origin: str,
    destination: str,
    departure_date: str | None = None,
    trip_type: TripType | None = None,
    requires_baggage: bool = False,
    with_pets: bool = False,
    max_price: float | None = None,
    min_driver_rating: float = 0.0,
    passenger_rating: float = 4.7,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    total_candidates = len(indexed_trips)

    for item in indexed_trips.values():
        if origin.casefold() not in item["origin"].casefold():
            continue
        if destination.casefold() not in item["destination"].casefold():
            continue
        if departure_date and not str(item["departure_at"]).startswith(departure_date):
            continue
        if trip_type and item["trip_type"] != trip_type.value:
            continue
        if requires_baggage and not item["allows_baggage"]:
            continue
        if with_pets and not item["allows_pets"]:
            continue
        if max_price is not None and float(item["price_per_seat"]) > max_price:
            continue
        if float(item["driver_rating"]) < min_driver_rating:
            continue

        route_overlap = 1.0 if item["origin"].casefold() == origin.casefold() else 0.72
        pref_match = (not requires_baggage or item["allows_baggage"]) and (not with_pets or item["allows_pets"])
        score = companion_score(passenger_rating, float(item["driver_rating"]), route_overlap, pref_match)
        results.append({**item, "match_score": score})

    results.sort(key=lambda trip: (-trip["match_score"], trip["departure_at"], trip["price_per_seat"]))
    plan = search_parallel_plan(total_candidates, regions=5)
    hit_ratio = cache_hits / max(cache_hits + cache_misses, 1)
    estimated = estimate_search_seconds(total_candidates, hit_ratio, plan["workers"])

    return {
        "items": results,
        "count": len(results),
        "search_time_estimate_seconds": estimated,
        "sla_seconds": settings.search_target_seconds,
        "sla_ok": estimated < settings.search_target_seconds,
        "parallel_plan": plan,
    }


@app.post("/search/index")
async def sync_index(request: IndexSyncRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "search:read")
    indexed_trips.clear()
    for trip in request.trips:
        payload = trip.model_dump(mode="json")
        payload["driver_rating"] = 4.6
        payload["historical_fill"] = 0.65
        indexed_trips[trip.trip_id] = payload
    return {"indexed": len(indexed_trips)}


@app.post("/search/recommendations")
async def recommendations(request: RecommendationRequest) -> dict[str, Any]:
    picks = []
    for item in indexed_trips.values():
        if request.origin.casefold() not in item["origin"].casefold():
            continue
        if request.destination.casefold() not in item["destination"].casefold():
            continue
        score = companion_score(
            request.passenger_rating,
            float(item["driver_rating"]),
            1.0,
            (not request.requires_baggage or item["allows_baggage"]) and (not request.with_pets or item["allows_pets"]),
        )
        picks.append(
            {
                "trip_id": item["trip_id"],
                "driver_id": item["driver_id"],
                "driver_rating": item["driver_rating"],
                "score": score,
            }
        )
    picks.sort(key=lambda value: (-value["score"], -value["driver_rating"]))
    return {"user_id": request.user_id, "items": picks[:5], "count": min(len(picks), 5)}


@app.get("/search/parallel-plan")
async def parallel_plan(candidates: int = 100000, regions: int = 12) -> dict[str, int]:
    return search_parallel_plan(candidates, regions)


@app.get("/maps/geocode")
async def geocode(city: str) -> dict[str, Any]:
    point = _coords(city)
    if point is None:
        raise HTTPException(status_code=404, detail="City not found in local geocache dictionary")
    return {"city": city, "latitude": point[0], "longitude": point[1], "provider": settings.maps_provider_url}


@app.get("/maps/route-preview")
async def route_preview(origin: str, destination: str, provider: str = "openstreetmap") -> dict[str, Any]:
    distance = _route_distance_km(origin, destination)
    encoded_route = f"{origin}:{destination}".replace(" ", "+")
    provider_name = provider.casefold()
    if provider_name == "mapbox":
        url = f"{settings.mapbox_api_base}/directions/v5/mapbox/driving/{encoded_route}"
    else:
        url = f"{settings.maps_provider_url}/directions?route={encoded_route}"
    return {
        "origin": origin,
        "destination": destination,
        "distance_km_estimate": distance,
        "provider": provider_name,
        "preview_url": url,
    }


@app.get("/search/cache/stats")
async def cache_stats() -> dict[str, Any]:
    calls = cache_hits + cache_misses
    ratio = round(cache_hits / calls, 3) if calls else 0.0
    return {"hits": cache_hits, "misses": cache_misses, "hit_ratio": ratio, "indexed_trips": len(indexed_trips)}
