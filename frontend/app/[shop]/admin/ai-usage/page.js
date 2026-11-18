"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

const minutes = (n) => n == null ? "—" : new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(n);
const date = (s) => s ? new Date(s).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }) : "—";
const money = (n, currency) => n == null ? "—" : new Intl.NumberFormat("en-US", { style: "currency", currency: currency || "USD" }).format(n / 100);

function Stat({ title, value, children }) {
  return <div className="rounded-xl border border-indigo-100 bg-white p-5"><p className="text-sm font-medium text-slate-600">{title}</p><p className="mt-2 text-3xl font-bold text-slate-900">{value}</p>{children && <p className="mt-2 text-sm text-slate-600">{children}</p>}</div>;
}

export default function AIUsagePage() {
  const { shop } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    // Reset the request state when the shop or refresh request changes.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true); setError(""); setData(null);
    async function load() {
      try {
        const response = await fetch("/api/account/ai-usage", { cache: "no-store", signal: controller.signal });
        const result = await response.json();
        if (!response.ok) throw new Error(response.status === 401 ? "Please sign in to view your shop’s usage." : result.detail || "Unable to load usage.");
        if (result.shop_slug !== shop) throw new Error("Please sign in to this shop’s account.");
        setData(result);
      } catch (e) { if (e.name !== "AbortError") setError(e.message); }
      finally { if (!controller.signal.aborted) setLoading(false); }
    }
    load();
    return () => controller.abort();
  }, [shop, refresh]);
  const b = data?.billing;
  const base = `/${encodeURIComponent(shop || "")}/admin`;
  return <main className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
    <Link href={base} className="text-sm font-semibold text-indigo-700">Back to dashboard</Link>
    <section className="mt-4 rounded-2xl border border-indigo-100 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-4"><div><h1 className="text-2xl font-bold text-slate-900">AI Usage &amp; Billing</h1><p className="mt-1 text-slate-600">{data?.shop_name || "Your shop"}</p></div><button type="button" onClick={() => setRefresh(n => n + 1)} disabled={loading} className="rounded-lg border border-indigo-200 px-4 py-2 text-sm font-semibold text-indigo-700 disabled:opacity-50">{loading ? "Loading…" : "Refresh"}</button></div>
      {error && <div role="alert" className="mt-5 rounded-lg bg-red-50 p-4 text-red-800">{error} <Link href="/login" className="underline">Sign in</Link></div>}
      {loading && <p role="status" className="mt-5 text-slate-600">Loading your billing period and usage…</p>}
      {!loading && data && !b && <p className="mt-5 text-slate-700">{data.message}</p>}
      {b && <><div className="mt-5 flex flex-wrap gap-x-6 gap-y-2 text-sm text-slate-700"><p><strong>Billing period:</strong> {date(b.period_start)} – {date(b.period_end)}</p><p><strong>Status:</strong> {b.status === "trialing" ? "Free trial" : b.status?.replaceAll("_", " ")}</p></div>
      {b.cancel_at && <p className="mt-3 text-sm text-amber-800">Cancellation scheduled for {date(b.cancel_at)}.</p>}
      {!b.cancel_at && b.cancel_at_period_end && <p className="mt-3 text-sm text-amber-800">Your subscription ends at the close of this billing period.</p>}
      {b.status === "trialing" && <p className="mt-4 rounded-lg bg-indigo-50 p-4 text-indigo-900">Your free trial ends {date(b.trial_end)}. No usage charges apply during the trial.</p>}
      <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {b.metered && <><Stat title="AI minutes used" value={minutes(b.minutes_used)}>This billing period</Stat><Stat title="Included minutes" value={minutes(b.included_minutes)}>Per paid billing period</Stat><Stat title="Included minutes remaining" value={minutes(b.minutes_remaining)}>Resets each billing period</Stat><Stat title="Extra minutes" value={minutes(b.overage_minutes)}>{money(b.overage_rate_cents, b.currency)} per extra minute</Stat><Stat title="Usage charges so far" value={money(b.usage_cents, b.currency)}>Before taxes and invoice adjustments</Stat></>}
        <Stat title="Monthly plan price" value={money(b.monthly_base_cents, b.currency)}>Scheduling{data.ai_enabled ? " + AI Receptionist" : ""}, before taxes and discounts</Stat>
      </div>
      <div className="mt-5 rounded-xl bg-indigo-50 p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-semibold text-indigo-950">Estimated next invoice</h2><p className="mt-1 text-sm text-indigo-900">{b.next_invoice_cents == null ? "No upcoming invoice available" : `For ${date(b.next_invoice_at)}`}</p></div><p className="text-3xl font-bold text-indigo-950">{money(b.next_invoice_cents, b.currency)}</p></div></div>
      <p className="mt-4 text-sm text-slate-600">{b.note}</p><p className="mt-2 text-xs text-slate-500">Last checked {new Date(b.updated_at).toLocaleString()}</p></>}
      <Link href={`${base}/account`} className="mt-6 inline-block rounded-lg bg-indigo-700 px-4 py-2 text-sm font-semibold text-white">Manage subscription &amp; view invoices</Link>
    </section>
  </main>;
}
