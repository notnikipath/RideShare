from shared.rideshare_common import estimate_booking_seconds, estimate_search_seconds, fill_rate, refund_amount


def test_estimate_search_seconds() -> None:
    value = estimate_search_seconds(candidate_count=8000, cache_hit_ratio=0.7, workers=8)
    assert 0 < value < 4


def test_estimate_booking_seconds() -> None:
    value = estimate_booking_seconds(queue_depth=300, async_payment=True)
    assert 0 < value < 6


def test_fill_rate_is_ratio() -> None:
    assert fill_rate(total_seats=4, available_seats=1) == 0.75


def test_refund_amount_reduces_by_penalty() -> None:
    assert refund_amount(1000, penalty_rate=0.2) == 800
