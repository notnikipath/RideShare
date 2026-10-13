# RideShare

RideShare is a microservice platform for finding ride companions on intercity, suburban, and recurring carpool routes.

## Implemented modules

- `api-gateway` - orchestration, workflow endpoints, quality dashboard aggregation
- `trip-service` - trip creation, seat inventory, dynamic price preview, occupancy forecast
- `search-service` - route/date search, baggage and pets filters, recommendation ranking, geodata cache
- `booking-service` - seat booking lifecycle, payment confirmation, cancellation and refund states
- `payment-service` - online payment simulation, commission, async queue processing, refunds
- `rating-service` - mutual ratings, profiles, automatic and manual blocking
- `verification-service` - phone, passport, driver license verification
- `chat-service` - trip chat, realtime tracker points, emergency alerts
- `notification-service` - participant notifications and history
- `frontend` - React dispatcher/passenger dashboard

## Supported trip types

- Intercity
- Suburban
- Regular routes (carpool)

## Optional improvements implemented

- Dynamic pricing based on demand and departure urgency
- Companion recommendations by route and rating match score
- Occupancy forecast for driver planning
- Geodata caching for map requests
- Parallel search execution plan
- Asynchronous payment processing queue
- Realtime trip tracker
- Emergency button workflow with notifications

## Tech stack

- Backend: Python FastAPI microservices
- Data: PostgreSQL, Redis
- Queue: RabbitMQ
- Maps: OpenStreetMap and Mapbox-compatible preview endpoints
- Frontend: React + Vite

## Local run

```bash
cd RideShare
docker compose up --build -d
```

## Useful URLs

- Frontend: `http://localhost:31236`
- Gateway health: `http://localhost:31230/health`
- Services health: `http://localhost:31230/services/health`
- Swagger: `http://localhost:31230/docs`

## Validation

```bash
python -m ruff check .
python -m pytest -q
docker compose config
```

## Demo workflow

```bash
python scripts/demo_pipeline.py
```

## Sample data

```bash
python scripts/generate_sample_data.py
```

Result file: `data/samples/rideshare_events.json`
