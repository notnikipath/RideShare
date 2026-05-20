from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.rideshare_common import (
    PaymentChargeRequest,
    PaymentRecord,
    PaymentStatus,
    Role,
    Settings,
    build_audit_event,
    has_permission,
    refund_amount,
)

settings = Settings(service_name="payment-service", service_port=8504)
app = FastAPI(title="RideShare Payment Service", version="1.0.0")

payments: dict[str, PaymentRecord] = {}
refunds: list[dict[str, Any]] = []
pending_queue: list[str] = []
audit_log: list[dict[str, Any]] = []


class RefundRequest(BaseModel):
    penalty_rate: float = Field(default=0.1, ge=0, le=0.95)
    reason: str = "user_cancelled"
    actor_id: str
    actor_role: Role


RefundRequest.model_rebuild()


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
            object_type="payment",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


def _seed_demo() -> None:
    demo = PaymentRecord(
        payment_id="PAY-DEMO-1",
        booking_id="BOOK-DEMO-1",
        user_id="USR-301",
        amount=420,
        commission_amount=42,
        total_charged=462,
        provider="mockpay",
        status=PaymentStatus.SUCCEEDED,
        transaction_ref="TX-DEMO-1",
        processed_at=datetime.now(UTC),
    )
    payments[demo.payment_id] = demo


_seed_demo()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/payments/charge")
async def charge_payment(request: PaymentChargeRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "payment:charge")
    commission = round(request.amount * request.commission_rate, 2)
    record = PaymentRecord(
        payment_id=str(uuid4()),
        booking_id=request.booking_id,
        user_id=request.user_id,
        amount=request.amount,
        commission_amount=commission,
        total_charged=round(request.amount + commission, 2),
        provider=request.provider,
        status=PaymentStatus.QUEUED if request.async_processing else PaymentStatus.SUCCEEDED,
    )
    if request.async_processing:
        pending_queue.append(record.payment_id)
    else:
        record.transaction_ref = f"TX-{record.payment_id[:8]}"
        record.processed_at = datetime.now(UTC)
    payments[record.payment_id] = record
    _audit(
        request.actor_id,
        request.actor_role,
        "payment.charge",
        record.payment_id,
        {"booking_id": request.booking_id},
    )
    return record.model_dump(mode="json")


@app.post("/payments/process-pending")
async def process_pending(limit: int = 100) -> dict[str, Any]:
    processed: list[dict[str, Any]] = []
    for _ in range(min(limit, len(pending_queue))):
        payment_id = pending_queue.pop(0)
        record = payments.get(payment_id)
        if record is None:
            continue
        record.status = PaymentStatus.SUCCEEDED
        record.transaction_ref = f"TX-{payment_id[:8]}"
        record.processed_at = datetime.now(UTC)
        processed.append(record.model_dump(mode="json"))
    return {"processed": processed, "count": len(processed), "remaining": len(pending_queue)}


@app.get("/payments")
async def list_payments(
    booking_id: str | None = None,
    user_id: str | None = None,
    status: PaymentStatus | None = None,
) -> dict[str, Any]:
    items = []
    for item in payments.values():
        if booking_id and item.booking_id != booking_id:
            continue
        if user_id and item.user_id != user_id:
            continue
        if status and item.status != status:
            continue
        items.append(item.model_dump(mode="json"))
    items.sort(key=lambda entry: entry["created_at"], reverse=True)
    return {"items": items, "count": len(items)}


@app.get("/payments/{payment_id}")
async def get_payment(payment_id: str) -> dict[str, Any]:
    record = payments.get(payment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return record.model_dump(mode="json")


@app.post("/payments/{payment_id}/refund")
async def refund_payment(payment_id: str, request: RefundRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "payment:refund")
    record = payments.get(payment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    if record.status not in {PaymentStatus.SUCCEEDED, PaymentStatus.REFUNDED}:
        raise HTTPException(status_code=409, detail=f"Cannot refund payment in status {record.status.value}")

    refund_value = refund_amount(record.total_charged, request.penalty_rate)
    record.status = PaymentStatus.REFUNDED
    details = {
        "refund_id": str(uuid4()),
        "payment_id": payment_id,
        "booking_id": record.booking_id,
        "reason": request.reason,
        "penalty_rate": request.penalty_rate,
        "refund_amount": refund_value,
        "created_at": datetime.now(UTC).isoformat(),
    }
    refunds.append(details)
    _audit(request.actor_id, request.actor_role, "payment.refund", payment_id, details)
    return {"payment": record.model_dump(mode="json"), "refund": details}


@app.get("/payments/refunds/history")
async def refund_history() -> dict[str, Any]:
    return {"items": refunds, "count": len(refunds)}


@app.get("/payments/providers")
async def payment_providers() -> dict[str, Any]:
    return {
        "items": [
            {"name": "mockpay", "online": True, "supports_refund": True},
            {"name": "cloud_cards", "online": True, "supports_refund": True},
        ],
        "default_commission_rate": settings.payment_commission_rate,
    }


@app.get("/payments/queue/stats")
async def queue_stats() -> dict[str, Any]:
    return {"pending_payments": len(pending_queue), "processed_payments": len(payments) - len(pending_queue)}


@app.get("/audit")
async def get_audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}
