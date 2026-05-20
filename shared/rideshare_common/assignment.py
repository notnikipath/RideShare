from __future__ import annotations


def dynamic_price(base_price: float, demand_ratio: float, hours_to_departure: float) -> float:
    demand_factor = 1 + max(demand_ratio, 0.0) * 0.42
    urgency_factor = 1.0
    if hours_to_departure < 6:
        urgency_factor = 1.18
    elif hours_to_departure < 24:
        urgency_factor = 1.08
    return round(max(base_price * demand_factor * urgency_factor, base_price * 0.7), 2)


def forecast_fill_rate(current_fill_rate: float, days_to_departure: int, trend_score: float = 0.5) -> float:
    proximity_boost = max(0, 7 - max(days_to_departure, 0)) * 0.03
    trend_boost = min(max(trend_score, 0.0), 1.0) * 0.22
    projected = current_fill_rate + proximity_boost + trend_boost
    return round(min(max(projected, current_fill_rate), 1.0), 3)


def companion_score(
    passenger_rating: float,
    driver_rating: float,
    route_overlap_ratio: float,
    preference_match: bool,
) -> float:
    rating_component = (max(min(passenger_rating, 5), 0) + max(min(driver_rating, 5), 0)) / 10
    route_component = min(max(route_overlap_ratio, 0), 1) * 0.35
    preference_component = 0.2 if preference_match else 0.0
    return round(min(1.0, rating_component * 0.45 + route_component + preference_component), 3)


def search_parallel_plan(candidate_count: int, regions: int) -> dict[str, int]:
    workers = min(24, max(2, regions * 2, candidate_count // 900))
    batch_size = max(100, candidate_count // workers) if candidate_count else 100
    return {"workers": workers, "batch_size": batch_size, "candidate_count": candidate_count}
