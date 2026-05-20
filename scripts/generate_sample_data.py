from __future__ import annotations

import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

TRIP_TYPES = ["intercity", "suburban", "carpool"]
CITIES = ["Moscow", "Tver", "Khimki", "Zelenograd", "Odintsovo", "Mytishchi"]
RIDE_STATUSES = ["open", "full", "cancelled", "completed"]


def generate_record(index: int) -> dict:
    origin = random.choice(CITIES)
    destination = random.choice([city for city in CITIES if city != origin])
    seats_total = random.randint(1, 6)
    seats_left = random.randint(0, seats_total)
    trip_type = random.choice(TRIP_TYPES)
    return {
        "trip_id": f"TRIP-{index:06d}",
        "driver_id": f"DRV-{random.randint(1, 6000):04d}",
        "trip_type": trip_type,
        "origin": origin,
        "destination": destination,
        "departure_at": (datetime.now(UTC) + timedelta(minutes=index % 1440)).isoformat(),
        "total_seats": seats_total,
        "available_seats": seats_left,
        "price_per_seat": round(random.uniform(250, 3500), 2),
        "allows_baggage": random.choice([True, False]),
        "allows_pets": random.choice([True, False]),
        "status": random.choice(RIDE_STATUSES),
        "driver_rating": round(random.uniform(2.8, 5.0), 2),
        "bookings_count": random.randint(0, 8),
        "created_at": (datetime.now(UTC) - timedelta(minutes=index)).isoformat(),
    }


if __name__ == "__main__":
    random.seed(25)
    output = Path(__file__).resolve().parents[1] / "data" / "samples" / "rideshare_events.json"
    payload = [generate_record(index) for index in range(1, 12001)]
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(payload)} records to {output}")
