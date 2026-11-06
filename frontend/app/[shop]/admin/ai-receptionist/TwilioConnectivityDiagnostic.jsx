"use client";

import { useState } from "react";

// Only rendered in the isolated Test Shop #3 AI receptionist page.
export default function TwilioConnectivityDiagnostic() {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [claimBusy, setClaimBusy] = useState(false);
  const [claimStatus, setClaimStatus] = useState("");

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

  async function claimExistingRelay() {
    if (busy || claimBusy) return;
    setClaimBusy(true);
    setClaimStatus("");
    try {
      const response = await fetch("/api/ai-setup/voice-relay/claim-test-reserve", {
        method: "POST",
        credentials: "same-origin",
        headers: { Accept: "application/json" },
        cache: "no-store",
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Relay registration was blocked; no calls were activated.");
      }
      if (data.relay_number !== "+15077135447" || data.enabled_for_calls !== false || data.ready_for_customer_calls !== false) {
        throw new Error("Relay returned an unexpected state. Do not test calls.");
      }
      setClaimStatus("The pre-purchased number (507) 713-5447 is registered to Test Shop #3. Calls and SMS remain disabled.");
    } catch (err) {
      setClaimStatus(err.message || "Relay registration failed.");
    } finally {
      setClaimBusy(false);
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
      <div className="mt-5 border-t border-slate-200 pt-4">
        <p className="text-sm text-slate-600">Once Twilio verifies the purchased reserve DID, register it exclusively to this shop. This does not purchase another number, modify HighLevel, enable calls, or send SMS.</p>
        <button type="button" onClick={claimExistingRelay} disabled={busy || claimBusy}
          className="mt-3 rounded-xl bg-slate-900 px-5 py-3 font-bold text-white disabled:opacity-50">
          {claimBusy ? "Verifying existing number…" : "Register Purchased Twilio Relay"}
        </button>
        {claimStatus && <p role="status" className="mt-3 text-sm text-slate-800">{claimStatus}</p>}
      </div>
      {error && <p role="alert" className="mt-4 text-sm font-semibold text-red-700">{error}</p>}
    </section>
  );
}
