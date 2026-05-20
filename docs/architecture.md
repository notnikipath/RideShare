# Architecture

## Context

RideShare provides a secure workflow for finding and booking companions for intercity, suburban, and recurring carpool rides.

## Service map

- `api-gateway`: unified entry point, auth token issuing, end-to-end booking workflow, quality dashboard
- `trip-service`: trip CRUD, seat management, dynamic price preview, occupancy forecast
- `search-service`: route/date filtering, baggage and pets filters, recommendation ranking, geocache
- `booking-service`: booking lifecycle state machine (pending -> confirmed -> cancelled/refunded)
- `payment-service`: online payment simulation, commission handling, async queue and refunds
- `rating-service`: mutual ratings, profile aggregation, violation blocking
- `verification-service`: phone, passport, and driver license checks
- `chat-service`: trip discussion, realtime tracker, emergency events
- `notification-service`: push/sms/in-app notification queue
- `frontend`: React dashboard for operational visibility

## Infrastructure

- PostgreSQL for transactional storage
- Redis for geodata caching and fast lookups
- RabbitMQ for asynchronous payment and notification scenarios
- Docker Compose for local deployment

## Core workflows

1. Trip creation by driver in `trip-service`
2. Passenger search by route/date/filters in `search-service`
3. Booking creation in `booking-service`
4. Online charge in `payment-service`
5. Seat reservation in `trip-service`
6. Driver notification in `notification-service`
7. Chat and realtime tracker updates in `chat-service`

## Scalability notes

- Search service exposes parallel worker planning for large candidate sets
- Geodata cache improves repeated map and route lookup latency
- Async payment queue isolates transient payment provider delays
- Microservice split allows horizontal scaling by demand hotspot (search, booking, payment)
