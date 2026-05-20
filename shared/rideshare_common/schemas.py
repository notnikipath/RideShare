from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TripType(str, Enum):
    INTERCITY = "intercity"
    SUBURBAN = "suburban"
    CARPOOL = "carpool"


class TripStatus(str, Enum):
    OPEN = "open"
    FULL = "full"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class BookingStatus(str, Enum):
    PENDING_PAYMENT = "pending_payment"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentStatus(str, Enum):
    QUEUED = "queued"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


class VerificationStatus(str, Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    VERIFIED = "verified"
    REJECTED = "rejected"


class Role(str, Enum):
    PASSENGER = "passenger"
    DRIVER = "driver"
    MODERATOR = "moderator"
    ADMIN = "admin"
    SYSTEM = "system"


class MessageType(str, Enum):
    CHAT = "chat"
    EMERGENCY = "emergency"


class NotificationChannel(str, Enum):
    PUSH = "push"
    SMS = "sms"
    EMAIL = "email"
    IN_APP = "in_app"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class TripCreateRequest(BaseModel):
    driver_id: str
    trip_type: TripType
    origin: str
    destination: str
    departure_at: datetime
    total_seats: int = Field(gt=0, le=8)
    price_per_seat: float = Field(gt=0)
    allows_baggage: bool = True
    allows_pets: bool = False
    is_recurring: bool = False
    recurring_days: list[int] = Field(default_factory=list)
    actor_id: str
    actor_role: Role


class Trip(BaseModel):
    trip_id: str
    driver_id: str
    trip_type: TripType
    origin: str
    destination: str
    departure_at: datetime
    total_seats: int = Field(gt=0, le=8)
    available_seats: int = Field(ge=0)
    price_per_seat: float = Field(gt=0)
    allows_baggage: bool = True
    allows_pets: bool = False
    is_recurring: bool = False
    recurring_days: list[int] = Field(default_factory=list)
    status: TripStatus = TripStatus.OPEN
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SeatMutationRequest(BaseModel):
    seats: int = Field(gt=0, le=8)
    booking_id: str | None = None
    actor_id: str
    actor_role: Role


class BookingCreateRequest(BaseModel):
    user_id: str
    trip_id: str
    seats: int = Field(gt=0, le=8)
    unit_price: float = Field(gt=0)
    requires_baggage: bool = False
    with_pets: bool = False
    actor_id: str
    actor_role: Role


class BookingRecord(BaseModel):
    booking_id: str
    user_id: str
    trip_id: str
    seats: int = Field(gt=0, le=8)
    unit_price: float = Field(gt=0)
    subtotal_amount: float = Field(ge=0)
    commission_amount: float = Field(ge=0)
    total_amount: float = Field(ge=0)
    status: BookingStatus = BookingStatus.PENDING_PAYMENT
    requires_baggage: bool = False
    with_pets: bool = False
    payment_id: str | None = None
    cancellation_reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PaymentChargeRequest(BaseModel):
    booking_id: str
    user_id: str
    amount: float = Field(gt=0)
    commission_rate: float = Field(default=0.1, ge=0, le=0.5)
    provider: str = "mockpay"
    async_processing: bool = True
    actor_id: str
    actor_role: Role


class PaymentRecord(BaseModel):
    payment_id: str
    booking_id: str
    user_id: str
    amount: float = Field(gt=0)
    commission_amount: float = Field(ge=0)
    total_charged: float = Field(gt=0)
    provider: str
    status: PaymentStatus
    transaction_ref: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    processed_at: datetime | None = None


class RatingCreateRequest(BaseModel):
    trip_id: str
    author_id: str
    target_user_id: str
    score: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=500)
    actor_role: Role


class RatingRecord(BaseModel):
    rating_id: str
    trip_id: str
    author_id: str
    target_user_id: str
    score: int = Field(ge=1, le=5)
    comment: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class UserRatingProfile(BaseModel):
    user_id: str
    average_rating: float = Field(ge=0, le=5)
    ratings_count: int = Field(ge=0)
    low_score_count: int = Field(ge=0)
    is_blocked: bool = False
    blocked_reason: str | None = None


class VerificationRecord(BaseModel):
    user_id: str
    phone_verified: bool = False
    passport_verified: bool = False
    driver_license_verified: bool = False
    status: VerificationStatus = VerificationStatus.PENDING
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ChatMessage(BaseModel):
    message_id: str
    trip_id: str
    sender_id: str
    text: str
    message_type: MessageType = MessageType.CHAT
    booking_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TrackerPoint(BaseModel):
    trip_id: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    speed_kph: float = Field(ge=0, le=240)
    source: str = "driver_app"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AuditEvent(BaseModel):
    event_id: str
    actor_id: str
    actor_role: Role | str
    action: str
    object_type: str
    object_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BookTripWorkflowResult(BaseModel):
    trip: dict[str, Any]
    booking: dict[str, Any]
    payment: dict[str, Any]
    notification: dict[str, Any]
    search_sla_seconds: float
    booking_sla_seconds: float
    booked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class QualityTargets(BaseModel):
    search_seconds_target: float = 2.0
    booking_seconds_target: float = 5.0
    trips_per_day_target: int = 100000
