"use client";

import { useState } from "react";

// Only rendered in the isolated Test Shop #3 AI receptionist page.
export default function TwilioConnectivityDiagnostic() {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  async function checkConnection() {
    if (busy) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const response = await fetch("/api/ai-setup/voice-relay/provider-connectivity", {
        method: "GET",
        credentials: "same-origin",
        headers: { Accept: "application/json" },
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error(
          response.status === 401 || response.status === 403
            ? "Sign in as the Test Shop 3 owner to run this check."
            : "Twilio did not confirm the connection. No changes were made."
        );
      }
      const data = await response.json();
      if (data?.connected !== true || !Number.isInteger(data?.assigned_number_count)) {
        throw new Error("Unexpected connectivity result. No changes were made.");
      }
      setResult(data);
    } catch (err) {
      setError(err.message || "Unable to verify Twilio connection.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="bg-white rounded-3xl shadow-lg border border-amber-200 p-7">
      <h2 className="text-2xl font-extrabold text-slate-900">
        Twilio Connection — Test Shop 3 Only
      </h2>
      <p className="text-sm text-slate-600 mt-2">
        Read-only diagnostic. Checks Twilio credentials and the number inventory.
        It does not make calls, buy numbers, change routing, or activate voicemail.
      </p>
      <button
        type="button"
        onClick={checkConnection}
        disabled={busy}
        className="mt-4 rounded-xl bg-slate-900 px-5 py-3 font-bold text-white disabled:opacity-50"
      >
        {busy ? "Checking Twilio…" : "Check Twilio Connection"}
      </button>
      {result && (
        <div role="status" className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
          <p className="font-bold">Twilio API connection verified.</p>
          <p className="mt-1">Numbers assigned to this Twilio account: {result.assigned_number_count}</p>
          <p className="mt-1">Live voicemail relay and SMS delivery are not yet verified.</p>
        </div>
      )}
      {error && <p role="alert" className="mt-4 text-sm font-semibold text-red-700">{error}</p>}
    </section>
  );
}
