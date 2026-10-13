import React, { useEffect, useMemo, useState } from "react";

import { KpiCard } from "../components/KpiCard";
import { TaskBoard } from "../components/TaskBoard";

const gatewayUrl = (import.meta.env.VITE_API_GATEWAY_URL || "http://localhost:31230").replace(/\/+$/, "");

const emptyDashboard = {
  trip: {
    trip_id: "TRIP-DEMO-2",
    origin: "Moscow",
    destination: "Zelenograd",
    trip_type: "suburban",
    total_seats: 2,
    available_seats: 1,
    price_per_seat: 420,
    driver_id: "DRV-221",
    status: "open",
  },
  bookings: { items: [], count: 0 },
  ratings: { items: [], count: 0 },
  driver_profile: { average_rating: 0, ratings_count: 0, is_blocked: false },
  verification: { status: "pending", phone_verified: false, passport_verified: false, driver_license_verified: false },
  chat: { items: [], count: 0 },
  tracker: { items: [], count: 0 },
  notifications: { items: [], count: 0 },
  search_cache: { hit_ratio: 0, hits: 0, misses: 0 },
  fill_rate: { avg_fill_rate: 0, open_trips: 0, total_trips: 0 },
};

async function loadDashboard(tripId, userId) {
  const response = await fetch(`${gatewayUrl}/dashboard/${tripId}/${userId}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch dashboard: ${response.status}`);
  }
  return response.json();
}

export function DashboardPage() {
  const [tripId, setTripId] = useState("TRIP-DEMO-2");
  const [userId, setUserId] = useState("USR-301");
  const [theme, setTheme] = useState("light");
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);
  const [dashboard, setDashboard] = useState(emptyDashboard);

  useEffect(() => {
    let active = true;

    loadDashboard(tripId, userId)
      .then((payload) => {
        if (!active) {
          return;
        }
        setDashboard({ ...emptyDashboard, ...payload });
        setStatus("succeeded");
        setError(null);
      })
      .catch((err) => {
        if (!active) {
          return;
        }
        setStatus("failed");
        setError(err.message);
      });

    return () => {
      active = false;
    };
  }, [tripId, userId]);

  const statusLabel = useMemo(() => {
    if (status === "loading") {
      return "loading";
    }
    if (status === "failed") {
      return "Service unavailable";
    }
    return "live";
  }, [status]);

  const refresh = async () => {
    try {
      setStatus("loading");
      const payload = await loadDashboard(tripId, userId);
      setDashboard({ ...emptyDashboard, ...payload });
      setStatus("succeeded");
      setError(null);
    } catch (err) {
      setStatus("failed");
      setError(err.message);
    }
  };

  const trackerItems = dashboard.tracker?.items || [];
  const latestPoint = trackerItems[trackerItems.length - 1];
  const chatItems = dashboard.chat?.items || [];
  const notifications = dashboard.notifications?.items || [];
  const bookings = dashboard.bookings?.items || [];
  const verification = dashboard.verification || emptyDashboard.verification;
  const profile = dashboard.driver_profile || emptyDashboard.driver_profile;

  return (
    <div className={`app theme-${theme}`}>
      <div className="background-orb orb-a" />
      <div className="background-orb orb-b" />

      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow">RideShare Control Desk</p>
          <h1>Journey overview</h1>
          <p className="sub">
            This dashboard aggregates trip status, booking queue, verification checks, live chat, and route tracker
            updates from all RideShare microservices.
          </p>
          <div className="hero-badges">
            <span>Dynamic pricing</span>
            <span>Passenger recommendations</span>
            <span>Async payments</span>
            <span>Emergency workflow</span>
          </div>
        </div>

        <div className="hero-panel">
          <label>
            Trip ID
            <input value={tripId} onChange={(event) => setTripId(event.target.value)} placeholder="TRIP-DEMO-2" />
          </label>
          <label>
            User ID
            <input value={userId} onChange={(event) => setUserId(event.target.value)} placeholder="USR-301" />
          </label>
          <div className="hero-actions">
            <button onClick={refresh} disabled={status === "loading"}>Refresh dashboard</button>
            <button className="ghost" onClick={() => setTheme((current) => (current === "light" ? "dark" : "light"))}>
              Theme
            </button>
          </div>
          <p className="status-line" role="status" aria-live="polite">Status: {statusLabel}</p>
        </div>
      </header>

      <section className="kpi-grid">
        <KpiCard
          title="Search SLA"
          value={`${Math.round((dashboard.search_cache?.hit_ratio || 0) * 100)}%`}
          target="Cache hit ratio > 60%"
          ok={Number(dashboard.search_cache?.hit_ratio || 0) >= 0.6}
        />
        <KpiCard
          title="Trip Fill"
          value={`${Math.round((dashboard.fill_rate?.avg_fill_rate || 0) * 100)}%`}
          target="Higher fill means fewer empty seats"
          ok={Number(dashboard.fill_rate?.avg_fill_rate || 0) >= 0.5}
        />
        <KpiCard
          title="Driver Rating"
          value={Number(profile.average_rating || 0).toFixed(2)}
          target="Keep above 4.0"
          ok={Number(profile.average_rating || 0) >= 4.0}
        />
        <KpiCard
          title="Verification"
          value={String(verification.status || "pending")}
          target="Phone + passport required"
          ok={verification.phone_verified && verification.passport_verified}
        />
      </section>

      {error ? <div className="error-banner" role="alert">{error}</div> : null}

      <section className="content-grid">
        <article className="panel panel-featured">
          <div className="panel-head compact">
            <div>
              <p className="section-kicker">Trip Snapshot</p>
              <h2>
                {dashboard.trip?.origin} to {dashboard.trip?.destination}
              </h2>
            </div>
            <span className="pill">{dashboard.trip?.status}</span>
          </div>
          <p className="panel-copy">
            {dashboard.trip?.trip_id} is a {dashboard.trip?.trip_type} ride operated by {dashboard.trip?.driver_id}.
          </p>
          <div className="metrics-row">
            <div>
              <strong>{dashboard.trip?.available_seats || 0}</strong>
              <span>seats left</span>
            </div>
            <div>
              <strong>{dashboard.trip?.total_seats || 0}</strong>
              <span>total seats</span>
            </div>
            <div>
              <strong>{Math.round(dashboard.trip?.price_per_seat || 0)}</strong>
              <span>RUB per seat</span>
            </div>
            <div>
              <strong>{bookings.length}</strong>
              <span>booking records</span>
            </div>
          </div>
          <TaskBoard bookings={bookings} />
        </article>

        <article className="panel">
          <div className="panel-head compact">
            <div>
              <p className="section-kicker">Verification</p>
              <h2>User trust state</h2>
            </div>
            <span className="pill accent">{verification.status}</span>
          </div>
          <div className="signal-grid">
            <div className="signal-card">
              <span>Phone</span>
              <strong>{verification.phone_verified ? "Verified" : "Pending"}</strong>
            </div>
            <div className="signal-card">
              <span>Passport</span>
              <strong>{verification.passport_verified ? "Verified" : "Pending"}</strong>
            </div>
            <div className="signal-card">
              <span>Driver License</span>
              <strong>{verification.driver_license_verified ? "Verified" : "Pending"}</strong>
            </div>
            <div className="signal-card">
              <span>Blocked</span>
              <strong>{profile.is_blocked ? "Yes" : "No"}</strong>
            </div>
          </div>
        </article>

        <article className="panel">
          <div className="panel-head compact">
            <div>
              <p className="section-kicker">Chat</p>
              <h2>Trip discussion</h2>
            </div>
            <span className="pill">{chatItems.length} messages</span>
          </div>
          <div className="stack-list">
            {chatItems.length ? (
              chatItems.slice(-5).reverse().map((item) => (
                <div className="stack-item" key={item.message_id}>
                  <div>
                    <p className="stack-title">{item.sender_id}</p>
                    <p className="stack-sub">{item.text}</p>
                  </div>
                  <span>{item.message_type}</span>
                </div>
              ))
            ) : (
              <div className="empty-board">No messages yet.</div>
            )}
          </div>
        </article>

        <article className="panel">
          <div className="panel-head compact">
            <div>
              <p className="section-kicker">Live Tracker</p>
              <h2>Realtime movement</h2>
            </div>
            <span className="pill accent">{trackerItems.length} points</span>
          </div>
          <div className="signal-grid">
            <div className="signal-card">
              <span>Speed</span>
              <strong>{latestPoint ? `${Math.round(latestPoint.speed_kph)} km/h` : "No data"}</strong>
            </div>
            <div className="signal-card">
              <span>Latitude</span>
              <strong>{latestPoint ? Number(latestPoint.latitude).toFixed(4) : "N/A"}</strong>
            </div>
            <div className="signal-card">
              <span>Longitude</span>
              <strong>{latestPoint ? Number(latestPoint.longitude).toFixed(4) : "N/A"}</strong>
            </div>
            <div className="signal-card">
              <span>Source</span>
              <strong>{latestPoint ? latestPoint.source : "N/A"}</strong>
            </div>
          </div>
          <div className="stack-list">
            {trackerItems.slice(-4).reverse().map((point, index) => (
              <div className="stack-item" key={`${point.timestamp}-${index}`}>
                <div>
                  <p className="stack-title">{new Date(point.timestamp).toLocaleString()}</p>
                  <p className="stack-sub">
                    {Number(point.latitude).toFixed(3)}, {Number(point.longitude).toFixed(3)}
                  </p>
                </div>
                <span>{Math.round(point.speed_kph)} km/h</span>
              </div>
            ))}
          </div>
        </article>

        <article className="panel panel-analytics">
          <div className="panel-head compact">
            <div>
              <p className="section-kicker">Notifications</p>
              <h2>Delivery to participants</h2>
            </div>
            <span className="pill accent">{notifications.length} items</span>
          </div>
          <div className="timeline-list">
            {notifications.length ? (
              notifications.slice(-6).reverse().map((item, index) => (
                <div className="stack-item" key={`${item.subject}-${index}`}>
                  <div>
                    <p className="stack-title">{item.subject}</p>
                    <p className="stack-sub">{item.body}</p>
                  </div>
                  <span>{item.channel}</span>
                </div>
              ))
            ) : (
              <div className="empty-board">No notifications for this user yet.</div>
            )}
          </div>
        </article>
      </section>
    </div>
  );
}
