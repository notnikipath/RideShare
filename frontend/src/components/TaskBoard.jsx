import React from "react";

export function TaskBoard({ bookings }) {
  if (!bookings?.length) {
    return <div className="empty-board">No bookings yet. Run the booking workflow to populate this lane.</div>;
  }

  return (
    <section className="route-lane">
      {bookings.slice(0, 6).map((booking) => (
        <article className="route-stop" key={booking.booking_id}>
          <div>
            <p className="lesson-type">{booking.status}</p>
            <h4>{booking.booking_id}</h4>
            <div className="lesson-meta">
              <span>User: {booking.user_id}</span>
              <span>Trip: {booking.trip_id}</span>
            </div>
          </div>
          <span>{booking.seats} seat(s)</span>
        </article>
      ))}
    </section>
  );
}
