# API Overview

## Gateway

- `POST /auth/token`
- `POST /auth/verify`
- `GET /services/health`
- `POST /workflow/book-trip`
- `POST /workflow/cancel-booking`
- `POST /workflow/emergency-assist`
- `GET /quality/targets`
- `GET /dashboard/{trip_id}/{user_id}`

## Trip service

- `GET /trips`
- `GET /trips/{trip_id}`
- `POST /trips`
- `POST /trips/{trip_id}/seats/reserve`
- `POST /trips/{trip_id}/seats/release`
- `GET /drivers/{driver_id}/trips`
- `POST /trips/{trip_id}/price-preview`
- `POST /trips/{trip_id}/occupancy-forecast`

## Search service

- `GET /search/trips`
- `POST /search/index`
- `POST /search/recommendations`
- `GET /search/parallel-plan`
- `GET /maps/geocode`
- `GET /maps/route-preview`
- `GET /search/cache/stats`

## Booking service

- `GET /bookings`
- `GET /bookings/{booking_id}`
- `POST /bookings`
- `POST /bookings/{booking_id}/confirm-payment`
- `POST /bookings/{booking_id}/cancel`
- `POST /bookings/{booking_id}/mark-refunded`

## Payment service

- `POST /payments/charge`
- `POST /payments/process-pending`
- `GET /payments`
- `GET /payments/{payment_id}`
- `POST /payments/{payment_id}/refund`
- `GET /payments/refunds/history`

## Rating service

- `POST /ratings`
- `GET /ratings/trip/{trip_id}`
- `GET /ratings/user/{user_id}`
- `GET /users/{user_id}/profile`
- `POST /moderation/block/{user_id}`
- `POST /moderation/unblock/{user_id}`

## Verification service

- `POST /verification/phone/start`
- `POST /verification/phone/confirm`
- `POST /verification/passport`
- `POST /verification/license`
- `GET /verification/{user_id}`
- `GET /verification/{user_id}/eligibility`

## Chat service

- `POST /chat/messages`
- `GET /chat/{trip_id}/messages`
- `POST /chat/{trip_id}/emergency`
- `POST /tracker/{trip_id}/points`
- `GET /tracker/{trip_id}`
- `GET /tracker/{trip_id}/latest`

## Notification service

- `POST /notify/send`
- `POST /notify/booking`
- `POST /notify/cancellation`
- `POST /notify/emergency`
- `GET /notify/history`
