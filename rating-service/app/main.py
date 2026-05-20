from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from shared.rideshare_common import (
    RatingCreateRequest,
    RatingRecord,
    Role,
    Settings,
    UserRatingProfile,
    build_audit_event,
    has_permission,
)

settings = Settings(service_name="rating-service", service_port=8505)
app = FastAPI(title="RideShare Rating Service", version="1.0.0")

ratings: list[RatingRecord] = []
profiles: dict[str, UserRatingProfile] = {}
audit_log: list[dict[str, Any]] = []


class ModerationRequest(BaseModel):
    reason: str
    actor_id: str
    actor_role: Role


ModerationRequest.model_rebuild()


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
            object_type="rating",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


def _profile_for(user_id: str) -> UserRatingProfile:
    return profiles.setdefault(
        user_id,
        UserRatingProfile(
            user_id=user_id,
            average_rating=0,
            ratings_count=0,
            low_score_count=0,
            is_blocked=False,
        ),
    )


def _seed_demo() -> None:
    demo = RatingRecord(
        rating_id="RATE-DEMO-1",
        trip_id="TRIP-DEMO-2",
        author_id="USR-301",
        target_user_id="DRV-221",
        score=5,
        comment="Smooth and punctual ride",
        created_at=datetime.now(UTC),
    )
    ratings.append(demo)
    profile = _profile_for("DRV-221")
    profile.average_rating = 5.0
    profile.ratings_count = 1


_seed_demo()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/ratings")
async def create_rating(request: RatingCreateRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "rating:create")
    if request.author_id == request.target_user_id:
        raise HTTPException(status_code=400, detail="Author and target cannot be the same")

    record = RatingRecord(
        rating_id=str(uuid4()),
        trip_id=request.trip_id,
        author_id=request.author_id,
        target_user_id=request.target_user_id,
        score=request.score,
        comment=request.comment,
    )
    ratings.append(record)

    profile = _profile_for(request.target_user_id)
    new_count = profile.ratings_count + 1
    profile.average_rating = round((profile.average_rating * profile.ratings_count + request.score) / new_count, 2)
    profile.ratings_count = new_count
    if request.score <= 2:
        profile.low_score_count += 1
    if profile.ratings_count >= 3 and profile.average_rating < 2.5:
        profile.is_blocked = True
        profile.blocked_reason = "Automatic block due to sustained low rating"

    _audit(request.author_id, request.actor_role, "rating.create", record.rating_id, {"target": request.target_user_id})
    return {"rating": record.model_dump(mode="json"), "profile": profile.model_dump(mode="json")}


@app.get("/ratings/trip/{trip_id}")
async def trip_ratings(trip_id: str) -> dict[str, Any]:
    items = [item.model_dump(mode="json") for item in ratings if item.trip_id == trip_id]
    return {"trip_id": trip_id, "items": items, "count": len(items)}


@app.get("/ratings/user/{user_id}")
async def user_ratings(user_id: str) -> dict[str, Any]:
    items = [item.model_dump(mode="json") for item in ratings if item.target_user_id == user_id]
    return {"user_id": user_id, "items": items, "count": len(items)}


@app.get("/users/{user_id}/profile")
async def user_profile(user_id: str) -> dict[str, Any]:
    profile = _profile_for(user_id)
    return profile.model_dump(mode="json")


@app.post("/moderation/block/{user_id}")
async def block_user(user_id: str, request: ModerationRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "rating:moderate")
    profile = _profile_for(user_id)
    profile.is_blocked = True
    profile.blocked_reason = request.reason
    _audit(request.actor_id, request.actor_role, "rating.block_user", user_id, {"reason": request.reason})
    return profile.model_dump(mode="json")


@app.post("/moderation/unblock/{user_id}")
async def unblock_user(user_id: str, request: ModerationRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "rating:moderate")
    profile = _profile_for(user_id)
    profile.is_blocked = False
    profile.blocked_reason = None
    _audit(request.actor_id, request.actor_role, "rating.unblock_user", user_id)
    return profile.model_dump(mode="json")


@app.get("/moderation/blocked")
async def blocked_users() -> dict[str, Any]:
    items = [profile.model_dump(mode="json") for profile in profiles.values() if profile.is_blocked]
    return {"items": items, "count": len(items)}


@app.get("/ratings/top-drivers")
async def top_drivers(limit: int = 10) -> dict[str, Any]:
    drivers = [item for item in profiles.values() if item.user_id.startswith("DRV-")]
    drivers.sort(key=lambda item: (-item.average_rating, -item.ratings_count))
    return {"items": [item.model_dump(mode="json") for item in drivers[:limit]], "count": min(len(drivers), limit)}


@app.get("/audit")
async def get_audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}
