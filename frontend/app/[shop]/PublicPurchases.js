"use client";

import { useRef, useState } from "react";

const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export default function PublicPurchases({ apiBase, shop, offers }) {
  const [selection, setSelection] = useState("");
  const [phone, setPhone] = useState("");
  const [textLink, setTextLink] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const attempt = useRef(null);
  const offerKey = offer => `${offer.kind}:${offer.id}`;
  const selected = offers.find(offer => offerKey(offer) === selection) || offers[0];

  async function checkout(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    const key = JSON.stringify([offerKey(selected), phone, textLink]);
    if (attempt.current?.key !== key) attempt.current = { key, id: crypto.randomUUID() };
    try {
      const response = await fetch(`${apiBase}/api/payments/public-retail/${encodeURIComponent(shop)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          kind: selected.kind, item_id: selected.id, price_cents: selected.price_cents, phone, text_link: textLink, request_id: attempt.current.id,
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Unable to start checkout.");
      if (!result.checkout_url) {
        attempt.current = null;
        throw new Error(result.status === "paid" ? "This purchase is already paid." : "This checkout has closed. Try again.");
      }
      window.location.assign(result.checkout_url);
    } catch (failure) {
      setError(failure.message);
      setBusy(false);
    }
  }

  return (
    <section className="space-y-4 rounded-3xl border border-indigo-100 bg-white p-6 shadow-lg">
      <h2 className="text-2xl font-bold">Buy a service or package</h2>
      <p className="text-sm text-slate-600">Pay now and book your visit separately.</p>
      <form onSubmit={checkout} className="space-y-4">
        <fieldset disabled={busy} className="grid gap-2">
          <legend className="sr-only">Choose a prepaid offer</legend>
          {offers.map(offer => (
            <label key={offerKey(offer)}
              className="flex items-start gap-3 rounded-xl border border-slate-300 p-3 has-checked:border-indigo-600 has-checked:bg-indigo-50">
              <input type="radio" name="offer" checked={offer === selected}
                onChange={() => setSelection(offerKey(offer))} className="mt-1" />
              <span className="grow">
                <strong className="block">{offer.name}</strong>
                <span className="text-sm text-slate-600">
                  {offer.kind === "service"
                    ? `1 session · ${offer.duration_minutes} min${offer.staff ? ` · ${offer.staff}` : ""}`
                    : `${offer.sessions} sessions · Expires ${offer.expiration_duration} ${offer.expiration_duration === 1 ? offer.expiration_unit.replace(/s$/, "") : offer.expiration_unit} after purchase`}
                </span>
              </span>
              <strong>{currency.format(offer.price_cents / 100)}</strong>
            </label>
          ))}
        </fieldset>
        <label className="block font-semibold">Mobile number
          <input type="tel" autoComplete="tel" required maxLength={32} value={phone}
            onChange={event => setPhone(event.target.value)} className="mt-1 block w-full rounded-xl border border-slate-400 p-3" />
        </label>
        <p className="text-sm text-slate-600">Use this number when you book so the shop can find your prepaid sessions.</p>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={textLink} onChange={event => setTextLink(event.target.checked)} />
          Text me a copy of the payment link.
        </label>
        <button disabled={busy} className="w-full rounded-xl bg-indigo-700 px-4 py-3 font-bold text-white disabled:opacity-50">
          {busy ? "Opening Stripe Checkout…" : "Continue to secure payment"}
        </button>
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      </form>
    </section>
  );
}
