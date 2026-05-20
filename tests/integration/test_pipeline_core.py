from pathlib import Path

from fastapi.testclient import TestClient

from tests.integration.helpers import load_module

ROOT = Path(__file__).resolve().parents[2]

trip_module = load_module("trip_module", ROOT / "trip-service" / "app" / "main.py")
search_module = load_module("search_module", ROOT / "search-service" / "app" / "main.py")
booking_module = load_module("booking_module", ROOT / "booking-service" / "app" / "main.py")
payment_module = load_module("payment_module", ROOT / "payment-service" / "app" / "main.py")
rating_module = load_module("rating_module", ROOT / "rating-service" / "app" / "main.py")
verification_module = load_module("verification_module", ROOT / "verification-service" / "app" / "main.py")
chat_module = load_module("chat_module", ROOT / "chat-service" / "app" / "main.py")
notification_module = load_module("notification_module", ROOT / "notification-service" / "app" / "main.py")

trip_client = TestClient(trip_module.app)
search_client = TestClient(search_module.app)
booking_client = TestClient(booking_module.app)
payment_client = TestClient(payment_module.app)
rating_client = TestClient(rating_module.app)
verification_client = TestClient(verification_module.app)
chat_client = TestClient(chat_module.app)
notification_client = TestClient(notification_module.app)


def test_booking_payment_and_trip_flow() -> None:
    trip_response = trip_client.get("/trips/TRIP-DEMO-1")
    assert trip_response.status_code == 200
    trip = trip_response.json()

    booking_response = booking_client.post(
        "/bookings",
        json={
            "user_id": "USR-410",
            "trip_id": trip["trip_id"],
            "seats": 1,
            "unit_price": trip["price_per_seat"],
            "requires_baggage": True,
            "with_pets": False,
            "actor_id": "USR-410",
            "actor_role": "passenger",
        },
    )
    assert booking_response.status_code == 200
    booking = booking_response.json()

    payment_response = payment_client.post(
        "/payments/charge",
        json={
            "booking_id": booking["booking_id"],
            "user_id": "USR-410",
            "amount": booking["subtotal_amount"],
            "commission_rate": 0.1,
            "provider": "mockpay",
            "async_processing": False,
            "actor_id": "gateway",
            "actor_role": "system",
        },
    )
    assert payment_response.status_code == 200
    payment = payment_response.json()
    assert payment["status"] == "succeeded"

    confirm_response = booking_client.post(
        f"/bookings/{booking['booking_id']}/confirm-payment",
        json={"payment_id": payment["payment_id"], "actor_id": "gateway", "actor_role": "system"},
    )
    assert confirm_response.status_code == 200
    confirmed_booking = confirm_response.json()
    assert confirmed_booking["status"] == "confirmed"

    reserve_response = trip_client.post(
        f"/trips/{trip['trip_id']}/seats/reserve",
        json={"seats": 1, "booking_id": booking["booking_id"], "actor_id": "gateway", "actor_role": "system"},
    )
    assert reserve_response.status_code == 200

    notice_response = notification_client.post(
        "/notify/booking",
        json={
            "driver_id": trip["driver_id"],
            "trip_id": trip["trip_id"],
            "booking_id": booking["booking_id"],
            "seats": 1,
            "actor_role": "system",
        },
    )
    assert notice_response.status_code == 200

    cancel_response = booking_client.post(
        f"/bookings/{booking['booking_id']}/cancel",
        json={"reason": "change_of_plans", "actor_id": "USR-410", "actor_role": "system"},
    )
    assert cancel_response.status_code == 200

    refund_response = payment_client.post(
        f"/payments/{payment['payment_id']}/refund",
        json={"penalty_rate": 0.1, "reason": "change_of_plans", "actor_id": "USR-410", "actor_role": "system"},
    )
    assert refund_response.status_code == 200

    release_response = trip_client.post(
        f"/trips/{trip['trip_id']}/seats/release",
        json={"seats": 1, "booking_id": booking["booking_id"], "actor_id": "gateway", "actor_role": "system"},
    )
    assert release_response.status_code == 200


def test_search_verification_chat_and_rating_flow() -> None:
    search_response = search_client.get(
        "/search/trips",
        params={
            "origin": "Moscow",
            "destination": "Zelenograd",
            "requires_baggage": True,
        },
    )
    assert search_response.status_code == 200
    assert search_response.json()["count"] >= 1

    start_phone = verification_client.post(
        "/verification/phone/start",
        json={
            "user_id": "USR-777",
            "phone": "+79990001122",
            "actor_id": "USR-777",
            "actor_role": "passenger",
        },
    )
    assert start_phone.status_code == 200

    confirm_phone = verification_client.post(
        "/verification/phone/confirm",
        json={"user_id": "USR-777", "code": "4242", "actor_id": "USR-777", "actor_role": "passenger"},
    )
    assert confirm_phone.status_code == 200

    passport = verification_client.post(
        "/verification/passport",
        json={
            "user_id": "USR-777",
            "passport_number": "4510123456",
            "full_name": "Ivan Petrov",
            "actor_id": "USR-777",
            "actor_role": "passenger",
        },
    )
    assert passport.status_code == 200

    message = chat_client.post(
        "/chat/messages",
        json={
            "trip_id": "TRIP-DEMO-2",
            "sender_id": "USR-777",
            "text": "Can we meet near metro station?",
            "actor_role": "passenger",
        },
    )
    assert message.status_code == 200

    tracker = chat_client.post(
        "/tracker/TRIP-DEMO-2/points",
        json={
            "trip_id": "TRIP-DEMO-2",
            "latitude": 55.98,
            "longitude": 37.18,
            "speed_kph": 52,
            "actor_role": "driver",
        },
    )
    assert tracker.status_code == 200

    rating = rating_client.post(
        "/ratings",
        json={
            "trip_id": "TRIP-DEMO-2",
            "author_id": "USR-777",
            "target_user_id": "DRV-221",
            "score": 5,
            "comment": "Comfortable and safe ride",
            "actor_role": "passenger",
        },
    )
    assert rating.status_code == 200

    profile = rating_client.get("/users/DRV-221/profile")
    assert profile.status_code == 200
    assert profile.json()["average_rating"] >= 4
