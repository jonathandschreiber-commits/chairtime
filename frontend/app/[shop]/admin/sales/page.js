"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

const methods = {
  stripe: "Stripe",
  cash: "Cash",
  check: "Check",
  external_card: "External card terminal",
  bank_transfer: "Bank transfer",
  other: "Other",
};
const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

async function readStripeSale(id, signal) {
  const response = await fetch(`/api/payments/sales/${encodeURIComponent(id)}`, {
    cache: "no-store",
    signal,
  });
  const result = await response.json();
  if (!response.ok || !Number.isSafeInteger(result.refunded_cents) || result.refunded_cents < 0) {
    throw new Error(typeof result.detail === "string" ? result.detail : "Could not verify Stripe refunds.");
  }
  return result;
}

function withStripeRefund(row, refundedCents) {
  if (refundedCents > row.amount_cents) throw new Error("Stripe refund exceeds the sale amount.");
  return {
    ...row,
    refunded_cents: refundedCents,
    collected_cents: row.amount_cents - refundedCents,
    status: refundedCents === 0 ? "paid" : refundedCents === row.amount_cents ? "refunded" : "partially_refunded",
  };
}

function StripeSaleDetails({ id, formatDate, onRefund }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    setBusy(true);
    setError("");
    try {
      const result = await readStripeSale(id);
      onRefund(id, result.refunded_cents);
      setData(result);
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }

  return <div className="space-y-1">
    <button type="button" disabled={busy} onClick={load} className="text-blue-700 underline">
      {busy ? "Loading Stripe details…" : data ? "Refresh Stripe details" : "Receipt & refunds"}
    </button>
    {error && <p role="alert">{error}</p>}
    {data && <>
      {data.receipt_url ? <a href={data.receipt_url} target="_blank" rel="noopener noreferrer"
        className="block text-blue-700 underline">View Stripe receipt</a> : <p>No Stripe receipt available.</p>}
      {data.refunds.length ? data.refunds.map(refund => <p key={refund.id}>
        {formatDate(new Date(refund.created_at))} · {money.format(refund.amount_cents / 100)} · {refund.status}
        {refund.reason && <> · {refund.reason.replaceAll("_", " ")}</>}
      </p>) : <p>No refunds recorded in Stripe.</p>}
    </>}
  </div>;
}

export default function SalesPage() {
  const { shop } = useParams();
  const [range, setRange] = useState({ start: "", end: "" });
  const [appliedRange, setAppliedRange] = useState(range);
  const [method, setMethod] = useState("");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    const query = new URLSearchParams(Object.entries(appliedRange).filter(([, value]) => value));
    setError("");
    setData(null);
    fetch("/api/payments/sales?" + query, { signal: controller.signal })
      .then(async response => {
        const result = await response.json();
        if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Could not load sales.");
        // Retail payments include both standalone services and service packages.
        // Keep the Stripe total unavailable if any paid retail sale cannot be checked.
        const sales = [...result.sales];
        const retailIndexes = sales.flatMap((row, index) => row.retail_details ? [index] : []);
        for (let offset = 0; offset < retailIndexes.length; offset += 5) {
          await Promise.all(retailIndexes.slice(offset, offset + 5).map(async index => {
            const row = sales[index];
            const details = await readStripeSale(row.id, controller.signal);
            sales[index] = withStripeRefund(row, details.refunded_cents);
          }));
        }
        if (!controller.signal.aborted) setData({ ...result, sales });
      })
      .catch(failure => { if (!controller.signal.aborted) setError(failure.message); });
    return () => controller.abort();
  }, [appliedRange]);

  function updateStripeRefund(id, refundedCents) {
    setData(previous => previous && ({
      ...previous,
      sales: previous.sales.map(row => row.id === id ? withStripeRefund(row, refundedCents) : row),
    }));
  }

  const rows = data?.sales ?? [];
  const filtered = rows.filter(row => !method || row.method === method);
  const net = stripe => money.format(rows.filter(row => (row.method === "stripe") === stripe)
    .reduce((total, row) => total + row.collected_cents, 0) / 100);
  const date = new Intl.DateTimeFormat("en-US", {
    dateStyle: "short", timeStyle: "short", timeZone: data?.timezone,
  });

  return (
    <main className="mx-auto max-w-6xl space-y-4 px-5 py-8">
      <Link href={`/${shop}/admin`} className="text-blue-700 underline">Admin Home</Link>
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-bold">Sales</h1>
        <Link href={`/${shop}/admin/retail`} className="rounded-xl bg-indigo-700 px-4 py-2 font-bold text-white">Sell or record payment</Link>
      </header>
      <form className="flex flex-wrap items-end gap-3 rounded-xl border bg-white p-4" onSubmit={event => {
        event.preventDefault();
        setAppliedRange({ ...range });
      }}>
        <label>From<input type="date" value={range.start} onChange={event => setRange({ ...range, start: event.target.value })} className="block rounded border p-2" /></label>
        <label>Through<input type="date" value={range.end} onChange={event => setRange({ ...range, end: event.target.value })} className="block rounded border p-2" /></label>
        <button className="rounded-lg bg-indigo-700 px-4 py-2 text-white">Apply dates</button>
        <label>Payment method<select value={method} onChange={event => setMethod(event.target.value)} className="block rounded border p-2">
          <option value="">All methods</option>
          {Object.entries(methods).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select></label>
      </form>
      {error && <p role="alert" className="text-red-800">{error}</p>}
      {!data && !error && <p role="status">Loading sales…</p>}
      {data && <>
        <div className="grid gap-3 sm:grid-cols-2">
          <p className="rounded-xl border bg-white p-4">Stripe collected, less recorded refunds <strong className="block text-xl">{net(true)}</strong></p>
          <p className="rounded-xl border bg-white p-4">Payments recorded outside Stripe <strong className="block text-xl">{net(false)}</strong></p>
        </div>
        <div className="overflow-x-auto rounded-xl border bg-white">
          <table className="w-full text-left text-sm">
            <thead><tr className="bg-slate-50">
              {["Date", "Customer", "Item", "Method", "Amount", "Status", "Details"].map(label => <th className="p-3" key={label}>{label}</th>)}
            </tr></thead>
            <tbody>{filtered.map(row => (
              <tr key={row.id} className="border-t">
                <td className="whitespace-nowrap p-3">{date.format(new Date(row.date))}</td>
                <td className="p-3">{row.customer || row.phone || "—"}</td>
                <td className="p-3">{row.item}</td>
                <td className="p-3">{methods[row.method]}</td>
                <td className="p-3">{money.format(row.amount_cents / 100)}</td>
                <td className="p-3 capitalize">{row.status.replaceAll("_", " ")}</td>
                <td className="p-3">
                  {row.appointment_id && <Link className="text-blue-700 underline" href={`/${shop}/admin/payments/${encodeURIComponent(row.appointment_id)}`}>Payment details</Link>}
                  {row.retail_details && <StripeSaleDetails id={row.id} formatDate={date.format} onRefund={updateStripeRefund} />}
                  {row.refunded_cents > 0 && <p>{money.format(row.refunded_cents / 100)} refunded</p>}
                  {row.recorded_by && <p>Recorded by {row.recorded_by}</p>}
                  {row.reference && <p>{row.reference}</p>}
                </td>
              </tr>
            ))}</tbody>
          </table>
          {!filtered.length && <p className="p-4">No sales match these filters.</p>}
        </div>
      </>}
    </main>
  );
}
