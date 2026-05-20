from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.rideshare_common import (
    Role,
    Settings,
    VerificationRecord,
    VerificationStatus,
    build_audit_event,
    decrypt_text,
    encrypt_text,
    has_permission,
)

settings = Settings(service_name="verification-service", service_port=8506)
app = FastAPI(title="RideShare Verification Service", version="1.0.0")

verifications: dict[str, VerificationRecord] = {}
phone_codes: dict[str, str] = {}
passport_store: dict[str, str] = {}
license_store: dict[str, str] = {}
audit_log: list[dict[str, Any]] = []


class PhoneStartRequest(BaseModel):
    user_id: str
    phone: str
    actor_id: str
    actor_role: Role


class PhoneConfirmRequest(BaseModel):
    user_id: str
    code: str
    actor_id: str
    actor_role: Role


class PassportVerifyRequest(BaseModel):
    user_id: str
    passport_number: str = Field(min_length=6)
    full_name: str = Field(min_length=3)
    actor_id: str
    actor_role: Role


class DriverLicenseVerifyRequest(BaseModel):
    user_id: str
    license_number: str = Field(min_length=5)
    categories: list[str] = Field(default_factory=list)
    actor_id: str
    actor_role: Role


class ModerationRequest(BaseModel):
    reason: str
    actor_id: str
    actor_role: Role


PhoneStartRequest.model_rebuild()
PhoneConfirmRequest.model_rebuild()
PassportVerifyRequest.model_rebuild()
DriverLicenseVerifyRequest.model_rebuild()
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
            object_type="verification",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


def _record(user_id: str) -> VerificationRecord:
    return verifications.setdefault(user_id, VerificationRecord(user_id=user_id))


def _update_status(record: VerificationRecord) -> None:
    if record.status == VerificationStatus.REJECTED:
        record.updated_at = datetime.now(UTC)
        return
    checks = [record.phone_verified, record.passport_verified, record.driver_license_verified]
    if all(checks):
        record.status = VerificationStatus.VERIFIED
    elif any(checks):
        record.status = VerificationStatus.PARTIAL
    else:
        record.status = VerificationStatus.PENDING
    record.updated_at = datetime.now(UTC)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/verification/phone/start")
async def start_phone_verification(request: PhoneStartRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "verification:update")
    code = "4242"
    phone_codes[request.user_id] = encrypt_text(code, settings.encryption_key)
    record = _record(request.user_id)
    _update_status(record)
    _audit(request.actor_id, request.actor_role, "verification.phone.start", request.user_id)
    return {
        "user_id": request.user_id,
        "status": "code_sent",
        "hint": "use code 4242 in demo mode",
        "masked_phone": f"***{request.phone[-4:]}" if len(request.phone) >= 4 else "***",
    }


@app.post("/verification/phone/confirm")
async def confirm_phone_verification(request: PhoneConfirmRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "verification:update")
    encrypted = phone_codes.get(request.user_id)
    if encrypted is None:
        raise HTTPException(status_code=404, detail="No pending phone verification")
    expected_code = decrypt_text(encrypted, settings.encryption_key)
    if request.code != expected_code:
        raise HTTPException(status_code=400, detail="Invalid verification code")

    record = _record(request.user_id)
    record.phone_verified = True
    _update_status(record)
    _audit(request.actor_id, request.actor_role, "verification.phone.confirm", request.user_id)
    return record.model_dump(mode="json")


@app.post("/verification/passport")
async def verify_passport(request: PassportVerifyRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "verification:update")
    if len(request.passport_number.strip()) < 6:
        raise HTTPException(status_code=400, detail="Passport number is too short")
    passport_store[request.user_id] = encrypt_text(
        f"{request.passport_number}:{request.full_name}",
        settings.encryption_key,
    )
    record = _record(request.user_id)
    record.passport_verified = True
    _update_status(record)
    _audit(request.actor_id, request.actor_role, "verification.passport", request.user_id)
    return record.model_dump(mode="json")


@app.post("/verification/license")
async def verify_driver_license(request: DriverLicenseVerifyRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "verification:update")
    if not request.categories:
        raise HTTPException(status_code=400, detail="At least one driver category is required")
    license_store[request.user_id] = encrypt_text(
        f"{request.license_number}:{','.join(request.categories)}",
        settings.encryption_key,
    )
    record = _record(request.user_id)
    record.driver_license_verified = True
    _update_status(record)
    _audit(request.actor_id, request.actor_role, "verification.license", request.user_id)
    return record.model_dump(mode="json")


@app.get("/verification/{user_id}")
async def get_verification(user_id: str) -> dict[str, Any]:
    record = _record(user_id)
    _update_status(record)
    return record.model_dump(mode="json")


@app.get("/verification/{user_id}/eligibility")
async def verification_eligibility(user_id: str, as_driver: bool = False) -> dict[str, Any]:
    record = _record(user_id)
    _update_status(record)
    if as_driver:
        eligible = record.phone_verified and record.passport_verified and record.driver_license_verified
    else:
        eligible = record.phone_verified and record.passport_verified
    return {"user_id": user_id, "eligible": eligible, "as_driver": as_driver, "status": record.status}


@app.post("/verification/reject/{user_id}")
async def reject_user(user_id: str, request: ModerationRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "rating:moderate")
    record = _record(user_id)
    record.status = VerificationStatus.REJECTED
    record.updated_at = datetime.now(UTC)
    _audit(request.actor_id, request.actor_role, "verification.reject", user_id, {"reason": request.reason})
    return record.model_dump(mode="json")


@app.get("/audit")
async def get_audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}
