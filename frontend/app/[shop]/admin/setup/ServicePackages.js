"use client";

import { useEffect, useState } from "react";

export default function ServicePackages({ catalog }) {
  const [offers, setOffers] = useState([]);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
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
    try {
      const response = await fetch("/api/payments/packages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          catalog_id: fields.get("service"),
          name: fields.get("name"),
          sessions: Number(fields.get("sessions")),
          price_cents: Math.round(Number(fields.get("price")) * 100),
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Could not save package.");
      setOffers(previous => [...previous, result]);
      form.reset();
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }

  if (!ready && !error) return null;

  return (
    <section className="space-y-4 rounded-2xl border border-indigo-200 bg-white p-6">
      <h2 className="text-2xl font-bold">Service Packages</h2>
      {error && <p role="alert" className="text-red-700">{error}</p>}
      {offers.map(offer => (
        <p key={offer.id}>{offer.name} · {offer.sessions} sessions · ${(offer.price_cents / 100).toFixed(2)}</p>
      ))}
      {ready && catalog.length === 0 && <p>Add a service above to create a package.</p>}
      {ready && catalog.length > 0 && (
        <form onSubmit={save} className="grid gap-3 sm:grid-cols-2">
          <label>Service
            <select required name="service" className="block w-full rounded border p-2">
              {catalog.map(service => <option key={service.id} value={service.id}>{service.name}</option>)}
            </select>
          </label>
          <label>Package name<input required maxLength={100} name="name" className="block w-full rounded border p-2" /></label>
          <label>Number of treatments<input required type="number" min={2} max={1000} name="sessions" className="block w-full rounded border p-2" /></label>
          <label>Total package price ($)<input required type="number" min="0.50" max="999999.99" step="0.01" name="price" className="block w-full rounded border p-2" /></label>
          <button disabled={busy} className="rounded bg-indigo-700 px-4 py-2 text-white disabled:opacity-50">Add package</button>
        </form>
      )}
    </section>
  );
}
