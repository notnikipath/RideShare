from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from .schemas import Role

PERMISSIONS: dict[Role, set[str]] = {
    Role.PASSENGER: {
        "trip:read",
        "search:read",
        "booking:create",
        "booking:read:own",
        "booking:cancel:own",
        "rating:create",
        "chat:send",
        "chat:read",
        "verification:update:own",
    },
    Role.DRIVER: {
        "trip:create",
        "trip:update:own",
        "trip:read",
        "booking:read:trip",
        "rating:create",
        "chat:send",
        "chat:read",
        "verification:update:own",
        "tracker:write",
    },
    Role.MODERATOR: {
        "trip:read",
        "booking:read",
        "rating:read",
        "rating:moderate",
        "verification:read",
        "chat:read",
        "chat:moderate",
        "notification:send",
    },
    Role.ADMIN: {
        "trip:create",
        "trip:update",
        "trip:read",
        "search:read",
        "booking:create",
        "booking:read",
        "booking:cancel",
        "payment:charge",
        "payment:refund",
        "payment:read",
        "rating:create",
        "rating:read",
        "rating:moderate",
        "verification:update",
        "verification:read",
        "chat:send",
        "chat:read",
        "chat:moderate",
        "notification:send",
        "audit:read",
        "tracker:write",
    },
    Role.SYSTEM: {
        "trip:update",
        "trip:read",
        "search:read",
        "booking:create",
        "booking:read",
        "booking:cancel",
        "payment:charge",
        "payment:refund",
        "payment:read",
        "rating:read",
        "verification:read",
        "chat:read",
        "notification:send",
        "tracker:write",
    },
}


def has_permission(role: Role | str, action: str) -> bool:
    normalized = Role(role) if isinstance(role, str) else role
    allowed = PERMISSIONS.get(normalized, set())
    if action in allowed:
        return True
    if f"{action}:own" in allowed:
        return True
    if action.endswith(":own") and action[:-4] in allowed:
        return True
    return False


def _derive_key(secret: str) -> bytes:
    return hashlib.sha256(secret.encode("utf-8")).digest()


def sign_token(payload: dict[str, Any], secret: str, exp_minutes: int = 180) -> str:
    data = dict(payload)
    data["exp"] = int((datetime.now(UTC) + timedelta(minutes=exp_minutes)).timestamp())
    payload_b64 = base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode("utf-8")).decode("ascii")
    signature = hmac.new(_derive_key(secret), payload_b64.encode("ascii"), hashlib.sha256).digest()
    signature_b64 = base64.urlsafe_b64encode(signature).decode("ascii")
    return f"{payload_b64}.{signature_b64}"


def verify_token(token: str, secret: str) -> dict[str, Any] | None:
    try:
        payload_b64, signature_b64 = token.split(".", maxsplit=1)
        expected = hmac.new(_derive_key(secret), payload_b64.encode("ascii"), hashlib.sha256).digest()
        received = base64.urlsafe_b64decode(signature_b64.encode("ascii"))
        if not hmac.compare_digest(expected, received):
            return None
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode("ascii")).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(datetime.now(UTC).timestamp()):
            return None
        return payload
    except Exception:
        return None


def encrypt_text(value: str, key: str) -> str:
    if not value:
        return value
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    raw = value.encode("utf-8")
    out = bytes([raw[idx] ^ digest[idx % len(digest)] for idx in range(len(raw))])
    return base64.urlsafe_b64encode(out).decode("ascii")


def decrypt_text(value: str, key: str) -> str:
    if not value:
        return value
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    data = base64.urlsafe_b64decode(value.encode("ascii"))
    raw = bytes([data[idx] ^ digest[idx % len(digest)] for idx in range(len(data))])
    return raw.decode("utf-8")
