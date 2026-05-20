# Algorithms

## Dynamic pricing

`price = base_price * (1 + demand_ratio * 0.42) * urgency_factor`

- `urgency_factor = 1.18` if departure is under 6 hours
- `urgency_factor = 1.08` if departure is under 24 hours
- otherwise `urgency_factor = 1.00`

## Occupancy forecast

`projected_fill = current_fill + proximity_boost + trend_boost`

- `proximity_boost` grows when departure date is near
- `trend_boost` follows historical route demand
- final value is clamped to `[current_fill, 1.0]`

## Companion recommendation score

`score = rating_component * 0.45 + route_component + preference_component`

- `rating_component` from passenger and driver ratings
- `route_component` from overlap between requested and offered route
- `preference_component` bonus for baggage/pet preference match

## SLA estimation

- Search SLA estimate uses candidate count, cache hit ratio, and worker parallelism
- Booking SLA estimate uses queue depth and async payment flag
