"use client";

import { useEffect, useState } from "react";

export default function AccountBalance({ appointmentId }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let controller;
    async function load() {
      controller?.abort();
      const request = new AbortController();
      controller = request;
      try {
        const response = await fetch(`/api/payments/appointments/${encodeURIComponent(appointmentId)}/manual-sessions`, {
          cache: "no-store", signal: request.signal,
        });
        if (!response.ok) throw new Error("Could not load balance.");
        const result = await response.json();
        if (!request.signal.aborted) {
          setData(result);
          setError(false);
        }
      } catch {
        if (!request.signal.aborted) setError(true);
      }
    }

    function refresh(event) {
      if (event.detail === appointmentId) load();
    }

    load();
    window.addEventListener("daytello-session-adjusted", refresh);
    return () => {
      controller?.abort();
      window.removeEventListener("daytello-session-adjusted", refresh);
    };
  }, [appointmentId]);

  if (error) return <p className="mb-3 text-sm" role="status">Account balance unavailable.</p>;
  if (!data) return null;
  const total = data.balances.reduce((sum, balance) => sum + balance.sessions, 0);
  const formatDate = new Intl.DateTimeFormat(undefined, {
    dateStyle: "short", timeStyle: "short", timeZone: data.timezone,
  });

  const purchaseDate = new Intl.DateTimeFormat(undefined, { dateStyle: "short", timeZone: data.timezone });

  return (
    <details className="mb-3 rounded-xl border border-purple-200 bg-purple-50 p-3 text-sm">
      <summary className="cursor-pointer font-semibold">
        Account Balance: {total} {total === 1 ? "session" : "sessions"} available
      </summary>
      <div className="mt-2 space-y-2 pl-4">
        {data.balances.map(balance => (
          <p key={balance.id}>
            <strong>{balance.name}</strong> · {balance.method} · {balance.sessions} available
            {balance.purchased_at && <> · Purchased <time dateTime={balance.purchased_at}>{purchaseDate.format(new Date(balance.purchased_at))}</time></>}
            {balance.refund_status && ` · ${balance.refund_status}`}
          </p>
        ))}
        {data.history.map(entry => (
          <p key={entry.id}>
            <strong>Manual Adjustment</strong> · {Math.abs(entry.delta)} {entry.delta > 0 ? "added" : "deducted"} for {entry.service}
            {" on "}<time dateTime={entry.at}>{formatDate.format(new Date(entry.at))}</time>
            {entry.owner && ` by ${entry.owner}`} · {entry.reason}
          </p>
        ))}
        {!data.balances.length && !data.history.length && <p>No prepaid sessions.</p>}
      </div>
    </details>
  );
}
