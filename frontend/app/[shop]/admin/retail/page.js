"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

async function retailRequest(path, options) {
  const response = await fetch("/api/payments/retail" + path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Unable to process the sale.");
  return data;
}

export default function RetailPage() {
  const { shop } = useParams();
  const [catalog, setCatalog] = useState(null);
  const [query, setQuery] = useState("");
  const [customers, setCustomers] = useState([]);
  const [phone, setPhone] = useState("");
  const [choice, setChoice] = useState("");
  const [method, setMethod] = useState("");
  const [reference, setReference] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const draft = useRef(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    retailRequest("").then(data => {
      setCatalog(data);
      const service = data.services.find(item => item.catalog_id === params.get("service"));
      if (data.packages.some(item => item.id === params.get("package"))) {
        setChoice("package:" + params.get("package"));
      } else if (service && data.services.filter(item => item.catalog_id === service.catalog_id).length === 1) {
        setChoice("service:" + service.id);
      }
    }).catch(failure => setError(failure.message));
  }, []);

  useEffect(() => {
    if (query.trim().length < 2) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      retailRequest("/customers?q=" + encodeURIComponent(query), { signal: controller.signal })
        .then(setCustomers).catch(failure => {
          if (!controller.signal.aborted) setError(failure.message);
        });
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [query]);

  async function send(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    setStatus("");
    const [kind, item_id] = choice.split(":");
    const key = JSON.stringify([kind, item_id, phone, method, reference]);
    if (draft.current?.key !== key) draft.current = { key, id: crypto.randomUUID() };
    try {
      const result = await retailRequest("", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind, item_id, phone, method: method || null, reference, request_id: draft.current.id }),
      });
      const messages = {
        recorded: "Payment recorded. Prepaid sessions are available.",
        sent: "Payment link texted. Awaiting payment.",
        paid: "Stripe confirmed payment.",
        pending: "Awaiting payment.",
        expired: "Payment link expired. You can send a new one.",
        sending: "Text delivery is in progress.",
        unknown: "Text delivery could not be confirmed. Check with the customer before sending another link.",
      };
      if (result.status === "failed") throw new Error("Could not text the payment link. Try again.");
      setStatus(messages[result.status] || "Check the payment status.");
      if (result.status === "expired") draft.current = null;
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-xl space-y-4 px-5 py-8">
      <Link href={`/${shop}/admin`} className="text-blue-700 underline">Admin Home</Link>
      <Link href={`/${shop}/admin/sales`} className="ml-4 text-blue-700 underline">Sales</Link>
      <h1 className="text-3xl font-bold">Sell a Service or Package</h1>
      {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-red-800">{error}</p>}
      {status && <p role="status" className="rounded-xl bg-emerald-50 p-3 text-emerald-800">{status}</p>}
      <form onSubmit={send} className="space-y-4 rounded-2xl border bg-white p-5 shadow-sm">
        <label className="block font-semibold">Find a customer
          <input value={query} onChange={event => { setQuery(event.target.value); setCustomers([]); }}
            className="mt-1 block w-full rounded-lg border p-2" placeholder="Search name or phone" />
        </label>
        {customers.map(({ name, phone: number }) => (
          <button key={JSON.stringify([name, number])} type="button" className="mr-2 rounded-lg border px-3 py-2"
            onClick={() => { setPhone(number); setStatus(""); setQuery(""); setCustomers([]); }}>{name} · {number}</button>
        ))}
        <label className="block font-semibold">Customer mobile number
          <input required type="tel" value={phone} onChange={event => { setPhone(event.target.value); setStatus(""); }}
            className="mt-1 block w-full rounded-lg border p-2" />
        </label>
        <label className="block font-semibold">What are you selling?
          <select required value={choice} onChange={event => { setChoice(event.target.value); setStatus(""); }}
            className="mt-1 block w-full rounded-lg border p-2">
            <option value="">Choose a service or package</option>
            <optgroup label="Services">{catalog?.services.map(item => (
              <option key={item.id} value={"service:" + item.id}>
                {item.name} {item.staff ? `· ${item.staff}` : ""} · {item.duration_minutes} min · ${(item.price_cents / 100).toFixed(2)}
              </option>
            ))}</optgroup>
            <optgroup label="Packages">{catalog?.packages.map(item => (
              <option key={item.id} value={"package:" + item.id}>
                {item.name} · {item.sessions} sessions · ${(item.price_cents / 100).toFixed(2)} · {item.expiration_duration} {item.expiration_unit}
              </option>
            ))}</optgroup>
          </select>
        </label>
        <label className="block font-semibold">Payment method
          <select value={method} onChange={event => { setMethod(event.target.value); setStatus(""); }}
            className="mt-1 block w-full rounded-lg border p-2">
            <option value="">Stripe payment link</option>
            <option value="cash">Cash</option>
            <option value="check">Check</option>
            <option value="external_card">External card terminal</option>
            <option value="bank_transfer">Bank transfer</option>
            <option value="other">Other</option>
          </select>
        </label>
        {method && <>
          <label className="block font-semibold">Reference or note (optional)
            <input value={reference} onChange={event => setReference(event.target.value)} maxLength={250}
              className="mt-1 block w-full rounded-lg border p-2" />
          </label>
          <label className="flex gap-2"><input key={method} type="checkbox" required /> I already received this payment.</label>
        </>}
        <button disabled={busy || !catalog || (method && status.startsWith("Payment recorded."))} className="rounded-xl bg-indigo-700 px-4 py-3 font-bold text-white disabled:opacity-50">
          {busy ? "Saving…" : method ? "Record payment" : status === "Payment link texted. Awaiting payment." ? "Check payment status" : "Text payment link"}
        </button>
      </form>
    </main>
  );
}
