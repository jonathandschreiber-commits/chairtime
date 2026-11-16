"use client";

import { useCallback, useEffect, useState } from "react";

export default function AIUsageReview({ refreshKey }) {
  const [review, setReview] = useState(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(async (signal) => {
    try {
      const response = await fetch("/api/business/ai-usage", { cache: "no-store", signal });
      if (!response.ok) throw new Error("Voice AI usage could not be refreshed.");
      const data = await response.json();
      if (signal?.aborted) return;
      setReview(data);
      setError("");
    } catch (failure) {
      if (failure.name !== "AbortError" && !signal?.aborted) {
        setReview(null);
        setError(failure.message);
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => refresh(controller.signal), 0);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [refresh, refreshKey]);

  async function recordPlan(unlimited) {
    const label = unlimited ? "$97 AI Employee Unlimited is active" : "$97 AI Employee Unlimited is no longer active";
    if (!window.confirm(`Confirm that ${label} in HighLevel for this location. This updates the DayTello report only.`)) return;
    setSaving(true);
    setError("");
    try {
      const response = await fetch("/api/business/ai-plan", {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ location_id: review.location_id, unlimited }),
      });
      if (!response.ok) throw new Error("Plan status could not be saved. Refresh and try again.");
      await refresh();
    } catch (failure) {
      setError(failure.message);
    } finally {
      setSaving(false);
    }
  }

  const messages = {
    connected: "No monitored shops reached 140 minutes.",
    covered: "This HighLevel location is recorded as covered by AI Employee Unlimited.",
    empty: "There are no AI shop agents configured for this HighLevel location.",
    ambiguous: "Voice AI usage is unavailable because more than one shop is mapped to the same agent.",
    unavailable: review?.provider_http_status
      ? `HighLevel call logs are unavailable (HTTP ${review.provider_http_status}).`
      : "Voice AI usage is unavailable. Try refreshing the report.",
  };

  return (
    <section aria-labelledby="ai-usage-heading" className="rounded-2xl border border-violet-200 bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="ai-usage-heading" className="text-xl font-extrabold">HighLevel AI usage review</h2>
          <p className="mt-1 text-sm text-slate-600">Shops with 140 minutes of live Voice AI calls in the past 7 days.</p>
        </div>
        {review?.location_id && (
          <button type="button" disabled={saving} onClick={() => recordPlan(!review.unlimited)}
            className="rounded-xl bg-violet-700 px-4 py-2 text-sm font-bold text-white hover:bg-violet-800 disabled:opacity-50">
            {saving ? "Saving…" : review.unlimited ? "Remove Unlimited status" : "Confirm Unlimited is active"}
          </button>
        )}
      </div>
      {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
      {review?.shops.length ? (
        <ul className="mt-4 divide-y divide-amber-200 rounded-xl border border-amber-200 bg-amber-50">
          {review.shops.map((shop) => (
            <li key={shop.slug} className="flex flex-wrap justify-between gap-2 px-4 py-3">
              <strong>{shop.name}</strong><span className="font-bold tabular-nums">{shop.minutes} minutes</span>
            </li>
          ))}
        </ul>
      ) : review ? <p className="mt-3 text-sm text-slate-700">{messages[review.status]}</p>
        : !error && <p className="mt-3 text-sm text-slate-600">Checking HighLevel call logs…</p>}
      {review?.location_shop_count > 0 && (
        <p className="mt-3 text-xs text-slate-600">
          Unlimited applies to the HighLevel location ({review.location_shop_count} mapped AI shops).
          {" "}{review.unlimited == null ? "The location’s plan has not been confirmed in DayTello." :
            review.unlimited ? "Unlimited is recorded as active." : "Unlimited is recorded as inactive."}
        </p>
      )}
      {review?.unmonitored_shop_count > 0 && (
        <p className="mt-2 text-xs text-amber-800">{review.unmonitored_shop_count} AI shops have agents outside the monitored location or lack a saved location.</p>
      )}
    </section>
  );
}
