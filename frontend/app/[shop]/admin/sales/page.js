"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

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

  const [draft, setDraft] = useState(null);
  const amount = draft && /^\d+(\.\d{1,2})?$/.test(draft.amount) ? Math.round(Number(draft.amount) * 100) : 0;
  const full = amount > 0 && amount === data?.refundable_cents;
  const remove = full ? data.sessions_remaining : draft?.remove ? Number(draft.sessions) : 0;
  const valid = amount > 0 && amount <= data?.refundable_cents &&
    Number.isSafeInteger(remove) && remove >= 0 && remove <= data?.sessions_remaining &&
    (full || !draft?.remove || remove > 0);

  async function submitRefund(event) {
    event.preventDefault();
    if (!valid || busy) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`/api/payments/sales/${encodeURIComponent(id)}/refund`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({request_id: draft.requestId, amount_cents: amount,
          sessions_to_remove: remove, expected_sessions: data.sessions_remaining}),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Could not confirm the refund. Refresh before retrying.");
      onRefund(id, result.refunded_cents);
      setData(result);
      setDraft(null);
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }

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
        {refund.sessions_removed != null && <> · {refund.sessions_removed} sessions removed · {refund.sessions_remaining} left after refund</>}
      </p>) : <p>No refunds recorded in Stripe.</p>}
      {data.can_refund && data.refundable_cents > 0 && !draft &&
        <button type="button" disabled={busy} onClick={() => setDraft({requestId: crypto.randomUUID(), amount: "", remove: false, sessions: "1"})} className="text-blue-700 underline">Refund this purchase</button>}
      {draft && <form onSubmit={submitRefund} className="space-y-2 rounded border p-2">
        <p>{data.sessions_remaining} sessions remaining on this purchase</p>
        <label className="block">Refund amount ($) <input className="w-24 rounded border p-1" type="number" min="0.01" max={data.refundable_cents / 100} step="0.01" value={draft.amount} disabled={busy} onChange={event => setDraft({...draft, amount: event.target.value, requestId: crypto.randomUUID()})} required /></label>
        {full ? <p>A full refund removes all unused sessions on this purchase.</p> :
          <label className="block">Session adjustment <select disabled={busy} value={draft.remove ? "remove" : "keep"} onChange={event => setDraft({...draft, remove: event.target.value === "remove", requestId: crypto.randomUUID()})}>
            <option value="keep">Refund money only</option>
            {data.sessions_remaining > 0 && <option value="remove">Refund money and remove unused sessions</option>}
          </select></label>}
        {!full && draft.remove && <label className="block">Sessions to remove <input className="w-20 rounded border p-1" type="number" min="1" max={data.sessions_remaining} value={draft.sessions} disabled={busy} onChange={event => setDraft({...draft, sessions: event.target.value, requestId: crypto.randomUUID()})} required /></label>}
        {valid && <p role="status">Refund {money.format(amount / 100)} · Sessions remaining after refund: {data.sessions_remaining - remove}</p>}
        <div className="flex flex-wrap gap-2 pt-1">
          <button type="submit" className="min-h-10 rounded-lg bg-red-700 px-3 py-2 font-semibold text-white enabled:hover:bg-red-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-700 disabled:opacity-50" disabled={!valid || busy}>Confirm refund</button>
          <button type="button" className="min-h-10 rounded-lg border border-slate-400 bg-white px-3 py-2 font-semibold text-slate-800 enabled:hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700 disabled:opacity-50" disabled={busy} onClick={() => setDraft(null)}>Cancel</button>
        </div>
      </form>}
    </>}
  </div>;
}

export default function SalesPage() {
  return <Suspense fallback={<p role="status">Loading sales…</p>}><SalesReport /></Suspense>;
}

function SalesReport() {
  const { shop } = useParams();
  const params = useSearchParams();
  const [range, setRange] = useState(() => ({
    start: "", end: "", customer_phone: params.get("customer_phone") || "", customer_name: "",
  }));
  const [appliedRange, setAppliedRange] = useState(range);
  const [method, setMethod] = useState("");
  const [transactionType, setTransactionType] = useState("");
  const [revision, setRevision] = useState(0);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    const query = new URLSearchParams(Object.entries(appliedRange).filter(([, value]) => value));
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
        if (retailIndexes.some(index => sales[index].refunded_cents > 0)) {
          const refreshed = await fetch("/api/payments/sales?" + query, { signal: controller.signal });
          if (!refreshed.ok) throw new Error("Could not load recorded refunds.");
          const { sales: refreshedRows } = await refreshed.json();
          const reconciled = new Map(sales.map(row => [row.id, row]));
          if (!controller.signal.aborted) setData({
            ...result, sales: refreshedRows.map(row => reconciled.get(row.id) || row),
          });
        } else if (!controller.signal.aborted) {
          setData({ ...result, sales });
        }
      })
      .catch(failure => { if (!controller.signal.aborted) setError(failure.message); });
    return () => controller.abort();
  }, [appliedRange, revision]);

  function updateStripeRefund(id, refundedCents) {
    setRevision(value => value + 1);
    setData(previous => previous && ({
      ...previous,
      sales: previous.sales.map(row => row.id === id ? withStripeRefund(row, refundedCents) : row),
    }));
  }

  const rows = data?.sales ?? [];
  const filtered = rows.filter(row => (!method || row.method === method)
    && (!transactionType || (row.transaction_type || "sale") === transactionType));
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
        setError("");
        setData(null);
        setAppliedRange({ ...range });
      }}>
        <label>From<input type="date" value={range.start} onChange={event => setRange({ ...range, start: event.target.value })} className="block rounded border p-2" /></label>
        <label>Through<input type="date" value={range.end} onChange={event => setRange({ ...range, end: event.target.value })} className="block rounded border p-2" /></label>
        <label>Customer phone<input type="tel" value={range.customer_phone} onChange={event => setRange({ ...range, customer_phone: event.target.value })} className="block rounded border p-2" /></label>
        <label>Customer name<input type="search" value={range.customer_name} onChange={event => setRange({ ...range, customer_name: event.target.value })} className="block rounded border p-2" /></label>
        <label>Payment method<select value={method} onChange={event => setMethod(event.target.value)} className="block rounded border p-2">
          <option value="">All methods</option>
          {Object.entries(methods).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select></label>
        <label>Transaction type<select value={transactionType} onChange={event => setTransactionType(event.target.value)} className="block rounded border p-2">
          <option value="">All transactions</option>
          <option value="sale">Sales</option>
          <option value="refund">Refunds</option>
        </select></label>
        <button type="submit" className="rounded-lg bg-indigo-700 px-4 py-2 text-white">Apply filters</button>
      </form>
      {error && <p role="alert" className="text-red-800">{error}</p>}
      {!data && !error && <p role="status">Loading sales…</p>}
      {data && <>
        <p className="text-sm text-slate-600">Sales totals use purchase dates. Refund rows use refund dates.</p>
        <div className="grid gap-3 sm:grid-cols-2">
          <p className="rounded-xl border bg-white p-4">Stripe collected, less recorded refunds <strong className="block text-xl">{net(true)}</strong></p>
          <p className="rounded-xl border bg-white p-4">Payments recorded outside Stripe <strong className="block text-xl">{net(false)}</strong></p>
        </div>
        <div className="overflow-x-auto rounded-xl border bg-white">
          <table className="w-full text-left text-sm">
            <thead><tr className="bg-slate-50">
              {["Date", "Customer", "Item", "Type", "Method", "Amount", "Status", "Details"].map(label => <th className="p-3" key={label}>{label}</th>)}
            </tr></thead>
            <tbody>{filtered.map(row => (
              <tr key={row.id} className="border-t">
                <td className="whitespace-nowrap p-3">{date.format(new Date(row.date))}</td>
                <td className="p-3">{row.customer || row.phone || "—"}</td>
                <td className="p-3">{row.item}</td>
                <td className="p-3">{row.transaction_type === "refund" ? "Refund" : "Sale"}</td>
                <td className="p-3">{methods[row.method]}</td>
                <td className="p-3">{money.format(row.amount_cents / 100)}</td>
                <td className="p-3 capitalize">{row.status.replaceAll("_", " ")}</td>
                <td className="p-3">
                  {row.appointment_id && <Link className="text-blue-700 underline" href={`/${shop}/admin/payments/${encodeURIComponent(row.appointment_id)}`}>Payment details</Link>}
                  {row.retail_details && <StripeSaleDetails id={row.id} formatDate={date.format} onRefund={updateStripeRefund} />}
                  {row.refunded_cents > 0 && <p>{money.format(row.refunded_cents / 100)} refunded</p>}
                  {row.recorded_by && <p>Recorded by {row.recorded_by}</p>}
                  {row.sessions_removed != null && <p>Sessions removed: {row.sessions_removed} · Remaining: {row.sessions_remaining}</p>}
                  {row.reference && <p>{row.reference}</p>}
                </td>
              </tr>
            ))}</tbody>
          </table>
          {!filtered.length && <p className="p-4">No transactions match these filters.</p>}
        </div>
      </>}
    </main>
  );
}
