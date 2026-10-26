"use client";

import { useState } from "react";

export default function DayTelloTestOAuthPage() {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function connect() {
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch("/api/daytello/oauth/start", {
        method: "POST",
        credentials: "same-origin",
        headers: { Accept: "application/json" },
        cache: "no-store",
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.authorization_url) {
        throw new Error(data.detail || "Cannot start the HighLevel test connection.");
      }
      window.location.assign(data.authorization_url);
    } catch (error) {
      setMessage(error?.message || "Unable to connect.");
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-3xl font-bold">DayTello — test voicemail connection</h1>
      <p className="mt-4 text-slate-700">
        Administrator-only setup for the original Stan&apos;s Shop testing environment.
        This does not activate SMS notifications or change customer call routing.
      </p>
      <p className="mt-3 font-semibold text-amber-800">
        Connect only after the test backend has been deployed, the OAuth settings
        have been verified, and HighLevel&apos;s correct test location is selected.
      </p>
      <button
        type="button"
        disabled={busy}
        onClick={connect}
        className="mt-6 rounded-lg bg-blue-700 px-5 py-3 font-bold text-white disabled:opacity-50"
      >
        {busy ? "Preparing…" : "Connect test HighLevel location"}
      </button>
      {message && <p role="alert" className="mt-4 text-red-700">{message}</p>}
    </main>
  );
}
