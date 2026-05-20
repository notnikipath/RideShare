from __future__ import annotations

import json
import urllib.request

BASE = "http://localhost:8500"


def request(method: str, path: str, payload: dict | None = None) -> dict:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    result = request(
        "POST",
        "/workflow/book-trip",
        {
            "user_id": "USR-301",
            "trip_id": "TRIP-DEMO-2",
            "seats": 1,
            "requires_baggage": True,
            "with_pets": False,
            "payment_async": True,
        },
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
