"use client";

import { useEffect, useState } from "react";

function ExpirationFields({ offer }) {
  const [duration, setDuration] = useState(offer?.expiration_duration ?? 1);
  const [unit, setUnit] = useState(offer?.expiration_unit ?? "years");
  const expires = new Date();
  if (unit === "days") {
    expires.setDate(expires.getDate() + Number(duration));
  } else {
    const day = expires.getDate();
    expires.setDate(1);
    expires.setMonth(expires.getMonth() + Number(duration) * (unit === "years" ? 12 : 1));
    expires.setDate(Math.min(day, new Date(expires.getFullYear(), expires.getMonth() + 1, 0).getDate()));
  }

  return (
    <fieldset className="space-y-2 rounded-xl border border-rose-200 p-3 sm:col-span-2">
      <legend className="font-bold">Expiration period</legend>
      <div className="flex gap-2">
        <input aria-label="Expiration duration" name="expiration_duration" type="number" required min="1" max="3650" step="1"
          value={duration} onChange={event => setDuration(event.target.value)} className="w-24 rounded border p-2" />
        <select aria-label="Expiration unit" name="expiration_unit" value={unit} onChange={event => setUnit(event.target.value)} className="rounded border p-2">
          <option value="days">Days</option>
          <option value="months">Months</option>
          <option value="years">Years</option>
        </select>
      </div>
      {Number(duration) > 0 && <p>If purchased today, expires on {expires.toLocaleDateString("en-US")}.</p>}
      <label className="flex items-start gap-2"><input type="checkbox" required /> Confirm this expiration period</label>
    </fieldset>
  );
}


export default function ServicePackages({ catalog }) {
  const [offers, setOffers] = useState([]);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/payments/packages", { signal: controller.signal })
      .then(async response => {
        if (response.status === 403) return;
        if (!response.ok) throw new Error("Could not load packages.");
        setOffers(await response.json());
        setReady(true);
      })
      .catch(failure => { if (!controller.signal.aborted) setError(failure.message); });
    return () => controller.abort();
  }, []);

  async function save(event) {
    event.preventDefault();
    if (busy) return;
    const form = event.currentTarget;
    const fields = new FormData(form);
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch(editing ? `/api/payments/packages/${editing.id}/edit` : "/api/payments/packages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          catalog_id: fields.get("service"),
          name: fields.get("name"),
          sessions: Number(fields.get("sessions")),
          expiration_duration: Number(fields.get("expiration_duration")),
          expiration_unit: fields.get("expiration_unit"),
          price_cents: Math.round(Number(fields.get("price")) * 100),
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Could not save package.");
      setOffers(previous => editing ? previous.map(offer => offer.id === result.id ? result : offer) : [...previous, result]);
      setEditing(null);
      setNotice("Package saved.");
      form.reset();
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (busy || !deleting) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch(`/api/payments/packages/${deleting}/delete`, { method: "POST" });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Could not delete package.");
      setOffers(previous => previous.filter(offer => offer.id !== deleting));
      if (editing?.id === deleting) setEditing(null);
      setDeleting(null);
      setNotice("Package deleted.");
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }

  if (!ready && !error) return null;

  const inputClass = "mt-1 block w-full rounded-xl border border-rose-200 bg-white p-2.5";
  const actionClass = "rounded-xl bg-rose-700 px-3 py-2 font-bold text-white disabled:opacity-50";

  return (
    <section className="space-y-4 rounded-3xl border border-rose-200 bg-white p-6 text-rose-950 shadow-md">
      <h2 className="text-2xl font-extrabold">Service Packages</h2>
      {error && <p role="alert" className="text-red-700">{error}</p>}
      {notice && <p role="status" className="font-semibold text-green-700">{notice}</p>}
      {ready && catalog.length === 0 && <p>Add a service above to create a package.</p>}
      {ready && (catalog.length > 0 || editing) && (
        <form key={editing?.id || "new"} onSubmit={save} className="grid gap-3 rounded-2xl border border-rose-100 bg-rose-50 p-4 text-sm sm:grid-cols-2">
          <h3 className="font-bold sm:col-span-2">{editing ? "Edit package" : "Add package"}</h3>
          <label>Service
            {editing ? <>
              <input className={inputClass} value={catalog.find(item => item.id === editing.catalog_id)?.name || "Service unavailable"} readOnly />
              <input type="hidden" name="service" value={editing.catalog_id} />
            </> : <select required name="service" className={inputClass}>
              <option value="">Choose a service</option>
              {catalog.map(service => <option key={service.id} value={service.id}>{service.name}</option>)}
            </select>}
          </label>
          <label>Package name<input required maxLength={100} name="name" defaultValue={editing?.name} className={inputClass} /></label>
          <label>Number of treatments<input required type="number" min={2} max={1000} name="sessions" defaultValue={editing?.sessions} className={inputClass} /></label>
          <label>Total package price ($)<input required type="number" min="0.50" max="999999.99" step="0.01" name="price" defaultValue={editing ? (editing.price_cents / 100).toFixed(2) : ""} className={inputClass} /></label>
          <ExpirationFields offer={editing} />
          <div className="flex gap-2 sm:col-span-2">
            <button disabled={busy} className={actionClass}>{editing ? "Save changes" : "+ Add Package"}</button>
            {editing && <button type="button" disabled={busy} onClick={() => setEditing(null)} className="rounded-xl border px-3 py-2">Cancel</button>}
          </div>
        </form>
      )}
      {offers.map(offer => (
        <div key={offer.id} className="rounded-2xl border border-rose-200 p-4 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="font-extrabold">{offer.name}</h3>
              <p className="text-sm text-slate-600">{catalog.find(item => item.id === offer.catalog_id)?.name || "Service unavailable"} · {offer.sessions} treatments · ${(offer.price_cents / 100).toFixed(2)} · Expires after {offer.expiration_duration ?? 1} {offer.expiration_unit ?? "years"}</p>
            </div>
            <div className="flex gap-2 text-sm">
              <button type="button" disabled={busy} className={actionClass} onClick={() => { setEditing(offer); setDeleting(null); setNotice(""); setError(""); }}>Edit</button>
              <button type="button" disabled={busy} className="rounded-xl bg-red-600 px-3 py-2 font-bold text-white disabled:opacity-50" onClick={() => { setDeleting(offer.id); setNotice(""); setError(""); }}>Delete</button>
            </div>
          </div>
          {deleting === offer.id && (
            <div className="mt-3 space-y-2 border-t border-rose-100 pt-3 text-sm">
              <p>Delete this package from future sales? Customers can still redeem treatments they purchased.</p>
              <button type="button" disabled={busy} onClick={remove} className={actionClass}>Confirm delete</button>
              <button type="button" disabled={busy} onClick={() => setDeleting(null)} className="ml-2 rounded-xl border px-3 py-2">Cancel</button>
            </div>
          )}
        </div>
      ))}
    </section>
  );
}
