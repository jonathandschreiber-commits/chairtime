"use client";

import { useState } from "react";

export default function ManualAdjustments({ appointmentId, onSaved }) {
  const [data, setData] = useState(null);
  const [form, setForm] = useState({ service: "", direction: "add", count: "", reason: "", purchase: "" });
  const [requestId, setRequestId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const endpoint = `/api/payments/appointments/${encodeURIComponent(appointmentId)}/manual-sessions`;
  const balances = data?.balances.filter(item => item.service_id === form.service) ?? [];
  const purchase = balances.find(item => item.id === form.purchase);
  const count = Number(form.count);
  const deducting = form.direction === "deduct";
  const canSave = form.service && Number.isInteger(count) && count > 0 && count <= 1000 &&
    form.reason.trim() && (!deducting || (purchase && count <= purchase.sessions));

  function change(fields) {
    setForm(previous => ({ ...previous, ...fields }));
    setRequestId(null);
  }

  async function run(submit) {
    setBusy(true);
    setError("");
    try {
      let options = { cache: "no-store" };
      if (submit) {
        const id = requestId || crypto.randomUUID();
        setRequestId(id);
        options = {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ request_id: id, service_id: form.service,
            delta: deducting ? -count : count, reason: form.reason,
            purchase_id: deducting ? form.purchase : null }),
        };
      }
      const response = await fetch(endpoint, options);
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Could not update sessions.");
      setData(result);
      if (submit) {
        change({ count: "", reason: "", purchase: "" });
        onSaved?.();
      }
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <details className="mt-4 rounded-2xl border border-purple-200 bg-purple-50 p-4"
      onToggle={event => { if (event.currentTarget.open && !busy && !data) run(false); }}>
      <summary className="cursor-pointer font-bold">Manual Adjustments</summary>
      {error && <p role="alert" className="mt-2 text-red-700">{error}</p>}
      {busy && <p role="status" className="mt-2">Loading or saving sessions…</p>}
      {!data && error && <button type="button" disabled={busy} onClick={() => run(false)}>Retry</button>}
      {data && <>
        <form className="mt-3 space-y-3" onSubmit={event => { event.preventDefault(); if (canSave && !busy) run(true); }}>
          <fieldset disabled={busy} className="grid gap-3 sm:grid-cols-3">
            <label>Service
              <select className="block w-full rounded border p-2" value={form.service} onChange={event => change({ service: event.target.value, purchase: "" })} required>
                <option value="">Choose a service</option>
                {data.services.map(service => <option key={service.id} value={service.id}>{service.name}</option>)}
              </select>
            </label>
            <label>Adjustment
              <select className="block w-full rounded border p-2" value={form.direction} onChange={event => change({ direction: event.target.value, purchase: "" })}>
                <option value="add">Add sessions</option>
                <option value="deduct">Deduct sessions</option>
              </select>
            </label>
            <label>Number of sessions
              <input className="block w-full rounded border p-2" type="number" min="1" max={deducting && purchase ? Math.min(purchase.sessions, 1000) : 1000} value={form.count} onChange={event => change({ count: event.target.value })} required />
            </label>
            {deducting && <label className="sm:col-span-3">Balance to deduct from
              <select className="block w-full rounded border p-2" value={form.purchase} onChange={event => change({ purchase: event.target.value })} required>
                <option value="">{balances.length ? "Choose a balance" : "No eligible balance for this service"}</option>
                {balances.map(item => <option key={item.id} value={item.id}>{item.name} · {item.method} · {item.sessions} available · {item.id.slice(-8)}</option>)}
              </select>
            </label>}
            <label className="sm:col-span-3">Reason
              <textarea className="block w-full rounded border p-2" maxLength={500} value={form.reason} onChange={event => change({ reason: event.target.value })} required />
            </label>
          </fieldset>
          {canSave && <p>{deducting ? `Selected balance: ${purchase.sessions} → ${purchase.sessions - count} sessions` : `New manual balance: ${count} sessions`}</p>}
          <button className="rounded-xl bg-purple-700 px-4 py-2 font-semibold text-white disabled:opacity-50" disabled={busy || !canSave}>Save adjustment</button>
        </form>
        {data.history.length > 0 && <ul className="mt-4 space-y-2 border-t pt-3 text-sm">
          {data.history.map(entry => <li key={entry.id}>
            <strong>{entry.service} · {entry.delta > 0 ? "+" : ""}{entry.delta} sessions</strong>
            <p className="whitespace-pre-wrap">{entry.reason}</p>
            <p className="text-gray-600"><time dateTime={entry.at}>{new Intl.DateTimeFormat(undefined, {
              dateStyle: "medium", timeStyle: "short", timeZone: data.timezone,
            }).format(new Date(entry.at))}</time>{entry.owner && ` · ${entry.owner}`}</p>
          </li>)}
        </ul>}
      </>}
    </details>
  );
}
