"use client";

import { useEffect, useState } from "react";

const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export default function TwilioCostReview({ refreshKey }) {
  const [review, setReview] = useState(null);

  useEffect(() => {
    const controller = new AbortController();

    async function refresh() {
      try {
        const response = await fetch("/api/business/twilio-review", {
          cache: "no-store", signal: controller.signal,
        });
        if (!response.ok) throw new Error("Twilio review request failed");
        const data = await response.json();
        if (!controller.signal.aborted) setReview(data);
      } catch {
        if (!controller.signal.aborted) setReview({ status: "unavailable" });
      }
    }

    refresh();
    return () => controller.abort();
  }, [refreshKey]);

  return (
    <section aria-labelledby="twilio-review-heading" className="rounded-2xl border border-violet-200 bg-white p-5">
      <h2 id="twilio-review-heading" className="text-xl font-extrabold">Twilio relay cost review</h2>
      <p className="mt-1 text-sm text-slate-600">Shops with $25 or more in matched relay call charges over the past 30 days.</p>
      {!review && <p className="mt-3 text-sm text-slate-600">Checking Twilio call charges…</p>}
      {review?.status === "unavailable" && <p role="alert" className="mt-3 text-sm text-red-700">Twilio call charges are unavailable. Try refreshing the report.</p>}
      {review?.status === "connected" && (
        <>
          {review.shops.length ? (
            <ul className="mt-4 divide-y divide-amber-200 rounded-xl border border-amber-200 bg-amber-50">
              {review.shops.map((shop) => (
                <li key={shop.slug} className="px-4 py-3">
                  <div className="flex flex-wrap justify-between gap-2">
                    <strong>{shop.name}</strong>
                    <span className="font-bold tabular-nums">{money.format(shop.cost_cents / 100)}</span>
                  </div>
                  <p className="mt-1 text-xs text-slate-700">
                    Connected minutes · Inbound {shop.inbound_minutes ?? "—"} · Outbound {shop.outbound_minutes ?? "—"}
                  </p>
                </li>
              ))}
            </ul>
          ) : <p className="mt-3 text-sm text-slate-700">No shops reached $25 in matched charges.</p>}
          {review.partial && <p className="mt-2 text-xs text-amber-800">Some matched calls are missing prices. Shop charges may be higher.</p>}
        </>
      )}
      <p className="mt-3 text-xs text-slate-600">Phone number fees, recordings, and unmatched charges are excluded from this flag.</p>
    </section>
  );
}
