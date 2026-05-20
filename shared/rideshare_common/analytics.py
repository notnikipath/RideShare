from __future__ import annotations


def estimate_search_seconds(candidate_count: int, cache_hit_ratio: float, workers: int = 1) -> float:
    bounded_cache = min(max(cache_hit_ratio, 0.0), 1.0)
    bounded_workers = max(1, workers)
    complexity_penalty = max(candidate_count - 1500, 0) / 9000
    parallel_boost = 1 / min(8, bounded_workers)
    value = 1.9 + complexity_penalty - bounded_cache * 0.9 + parallel_boost * 0.6
    return round(max(0.35, value), 3)


def estimate_booking_seconds(queue_depth: int, async_payment: bool = True) -> float:
    queue_penalty = min(max(queue_depth, 0), 2000) / 1200
    async_bonus = 0.9 if async_payment else 0.0
    value = 3.3 + queue_penalty - async_bonus
    return round(max(0.8, value), 3)


def fill_rate(total_seats: int, available_seats: int) -> float:
    if total_seats <= 0:
        return 0.0
    booked = max(total_seats - max(available_seats, 0), 0)
    return round(min(booked / total_seats, 1.0), 3)


def refund_amount(total_amount: float, penalty_rate: float = 0.1) -> float:
    penalty = max(0.0, min(0.95, penalty_rate))
    return round(max(total_amount * (1 - penalty), 0.0), 2)
