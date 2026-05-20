from shared.rideshare_common import companion_score, dynamic_price, forecast_fill_rate, search_parallel_plan


def test_dynamic_price_grows_with_demand() -> None:
    base = 500.0
    low = dynamic_price(base, demand_ratio=0.1, hours_to_departure=24)
    high = dynamic_price(base, demand_ratio=0.9, hours_to_departure=3)
    assert high > low
    assert low >= base * 0.7


def test_forecast_fill_rate_stays_bounded() -> None:
    value = forecast_fill_rate(0.45, days_to_departure=2, trend_score=0.7)
    assert 0.45 <= value <= 1.0


def test_companion_score_prefers_matching_preferences() -> None:
    no_match = companion_score(4.8, 4.9, route_overlap_ratio=0.9, preference_match=False)
    match = companion_score(4.8, 4.9, route_overlap_ratio=0.9, preference_match=True)
    assert match > no_match


def test_search_parallel_plan_has_valid_shape() -> None:
    plan = search_parallel_plan(120_000, 18)
    assert plan["workers"] >= 2
    assert plan["batch_size"] >= 100
