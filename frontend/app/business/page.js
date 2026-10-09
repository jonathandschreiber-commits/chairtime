"use client";

import Link from "next/link";
import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

const money = (cents) => cents == null ? "—" : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(cents / 100);
function easternDate() {
  const parts = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date());
  const get = (type) => parts.find((part) => part.type === type).value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}
const providers = { highlevel: "HighLevel wallet usage (manual fallback)", highlevel_base: "HighLevel base plan", railway: "Railway", vercel: "Vercel", domain: "Domains", other: "Other" };
const fieldStyle = "w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-slate-900";
const buttonStyle = "rounded-xl bg-violet-700 px-5 py-3 font-bold text-white hover:bg-violet-800 disabled:opacity-50";
const newEntry = () => ({ request_id: crypto.randomUUID(), incurred_on: easternDate(), shop_slug: "", provider: "other", description: "", reference: "", amount: "", kind: "cost" });

export default function BusinessPage() {
  const router = useRouter();
  const [authorized, setAuthorized] = useState(false);
  const [denied, setDenied] = useState(false);
  const [month, setMonth] = useState("");
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showEntry, setShowEntry] = useState(false);
  const [entry, setEntry] = useState(null);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState("");
  const [details, setDetails] = useState(null);
  const sequence = useRef(0);
  const reportController = useRef(null);
  const activeMonth = useRef("");
  const saveLock = useRef(false);

  useEffect(() => {
    setMonth(easternDate().slice(0, 7));
    const controller = new AbortController();
    fetch("/api/auth/me", { cache: "no-store", signal: controller.signal }).then(async (response) => {
      if (response.status === 401) { router.replace("/login"); return; }
      const user = await response.json();
      if (!response.ok) throw new Error("Unable to verify access. Please refresh.");
      if (user.platform_admin !== true) { setDenied(true); return; }
      setAuthorized(true);
    }).catch((failure) => { if (failure.name !== "AbortError") setError(failure.message); });
    return () => { controller.abort(); reportController.current?.abort(); };
  }, [router]);

  const loadReport = useCallback(async (silent = false) => {
    if (!authorized || !month) return;
    const id = ++sequence.current;
    reportController.current?.abort();
    const controller = new AbortController();
    reportController.current = controller;
    if (!silent) setLoading(true);
    setError("");
    try {
      const response = await fetch(`/api/business/report?month=${encodeURIComponent(month)}`, { cache: "no-store", signal: controller.signal });
      if (response.status === 401) { router.replace("/login"); return; }
      if (response.status === 403) { setReport(null); setAuthorized(false); setDenied(true); return; }
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Could not load the report.");
      if (id === sequence.current && activeMonth.current === month) setReport(data);
    } catch (failure) {
      if (failure.name !== "AbortError" && id === sequence.current) setError(failure.message);
    } finally { if (id === sequence.current) setLoading(false); }
  }, [authorized, month, router]);

  useEffect(() => {
    activeMonth.current = month;
    setReport(null);
    setDetails(null);
    loadReport();
    const timer = setInterval(() => { if (document.visibilityState === "visible") loadReport(true); }, 120000);
    return () => { clearInterval(timer); ++sequence.current; reportController.current?.abort(); };
  }, [loadReport, month]);

  async function saveExpense(event) {
    event.preventDefault();
    if (saveLock.current) return;
    saveLock.current = true;
    setSaving(true); setError(""); setNotice("");
    try {
      const response = await fetch("/api/business/expenses", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(entry) });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Check the expense fields and try again.");
      setShowEntry(false); setEntry(null); setNotice("Expense saved. Costs remain recorded until you void the entry.");
      await loadReport();
    } catch (failure) { setError(failure.message); }
    finally { saveLock.current = false; setSaving(false); }
  }

  async function voidExpense(expense) {
    if (saveLock.current || !window.confirm(`Void this recorded expense: ${expense.description}? The audit entry will remain.`)) return;
    saveLock.current = true; setSaving(true); setError("");
    try {
      const response = await fetch(`/api/business/expenses/${expense.id}/void`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: "{}" });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Unable to void this expense.");
      setNotice("Expense voided."); await loadReport();
    } catch (failure) { setError(failure.message); }
    finally { saveLock.current = false; setSaving(false); }
  }

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.replace("/login"); router.refresh();
  }

  if (denied) return <main className="min-h-screen bg-slate-50 p-8"><div className="mx-auto max-w-xl rounded-2xl bg-white p-8"><h1 className="text-2xl font-bold">Private business dashboard</h1><p className="mt-3">Your account does not have access to this report.</p><Link className="mt-5 inline-block font-bold text-violet-700" href="/login">Back to sign in</Link></div></main>;
  if (!authorized) return <main className="min-h-screen bg-slate-50 p-8"><p>{error || "Checking your access…"}</p></main>;

  const rows = (report?.shops || []).filter((shop) => `${shop.name} ${shop.slug}`.toLowerCase().includes(search.toLowerCase()));
  const totals = report?.totals || {};
  const remaining = totals.remaining_after_shared_cents;
  const stats = [
    ["Subscription collections", totals.subscription_collected_cents, "Before refunds and tax exclusion"],
    ["Transaction fees collected", totals.transaction_fee_collected_cents, "ChairTime fees from shop card payments"],
    ["Net revenue", totals.revenue_cents, "After refunds, tax exclusion and adjustments"],
    ["After recorded costs", remaining, "Provisional · unrecorded costs excluded"],
  ];

  return <main className="min-h-screen bg-slate-50 px-4 py-8 text-slate-900 sm:px-8">
    <div className="mx-auto max-w-7xl">
      <header className="flex flex-wrap items-start justify-between gap-5">
        <div><p className="text-xs font-extrabold uppercase tracking-widest text-violet-700">ChairTime · Private business report</p><h1 className="mt-2 text-3xl font-extrabold sm:text-4xl">Revenue & costs</h1><p className="mt-2 text-slate-600">See what each shop contributes to your business.</p></div>
        <div className="flex flex-wrap items-center gap-3"><Link href="/joebarber/admin" className="text-sm font-bold text-slate-600">Joe Barber test shop</Link><button onClick={logout} className="rounded-xl border border-slate-300 bg-white px-4 py-2 font-bold">Log out</button></div>
      </header>
      <div className="mt-7 flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-wrap items-end gap-3"><label className="text-sm font-bold">Report month<input type="month" min="2020-01" max="2100-12" value={month} onChange={(e) => setMonth(e.target.value)} className={`${fieldStyle} mt-1`} /></label><button onClick={() => loadReport()} disabled={loading} className={buttonStyle}>{loading ? "Refreshing…" : "Refresh report"}</button></div>
        <p className="text-sm text-slate-500">{report ? `Updated ${new Date(report.checked_at).toLocaleString()} · auto-refresh every 2 minutes` : "Reading Stripe and HighLevel activity…"}</p>
      </div>
      {error && <div role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 p-4 text-red-800">{error} {report && "Displayed figures are from the last successful refresh."}</div>}
      {notice && <div role="status" className="mt-4 rounded-xl bg-emerald-50 p-4 text-emerald-900">{notice}</div>}
      {report?.stripe_mode === "test" && <div className="mt-5 rounded-xl border border-violet-200 bg-violet-50 px-5 py-3 font-bold text-violet-900">Stripe test mode · revenue figures are test transactions. HighLevel costs are actual wallet charges.</div>}
      {report?.warnings.map((warning) => <div key={warning} role="alert" className="mt-4 rounded-xl bg-red-50 p-4 text-red-800">{warning}</div>)}
      <section aria-label="Financial totals" className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{stats.map(([label, value, caption], index) => <div key={label} className={`rounded-2xl border p-5 ${index === 3 ? "border-violet-300 bg-violet-100" : "border-slate-200 bg-white"}`}><p className="text-sm font-bold text-slate-600">{label}</p><p className={`mt-2 text-3xl font-extrabold ${value < 0 ? "text-red-700" : "text-slate-950"}`}>{money(value)}</p><p className="mt-2 text-xs leading-relaxed text-slate-600">{caption}</p></div>)}</section>
      <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-relaxed text-amber-950"><strong>{report?.highlevel?.status === "connected" ? "HighLevel wallet costs are connected." : report?.highlevel?.status === "unavailable" ? "HighLevel costs could not be refreshed." : "HighLevel billing is not configured."}</strong> {report?.highlevel?.status === "connected" ? "Billed usage refreshes with this report. Shared and unmatched costs appear below. Dedicated number rentals, SMS with saved message IDs and Voice AI with matching call IDs are assigned to shops. Aggregated carrier fees, email charges and unmatched usage remain shared." : "Recorded manual costs remain visible. Refresh to retry the connection."} Agency subscription, hosting and other overhead require separate expense entries.</div>
      <section className="mt-7 overflow-hidden rounded-2xl border border-slate-200 bg-white">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 p-5"><div><h2 className="text-xl font-extrabold">By shop</h2><p className="mt-1 text-sm text-slate-500">Net revenue includes subscriptions and platform transaction fees.</p></div><label className="sr-only" htmlFor="shop-search">Find a shop</label><input id="shop-search" type="search" placeholder="Find a shop" value={search} onChange={(e) => setSearch(e.target.value)} className="rounded-xl border border-slate-300 px-3 py-2" /></div>
        <div className="overflow-x-auto"><table className="w-full min-w-[1050px] text-sm"><thead className="bg-slate-50 text-slate-600"><tr>{["Shop / current plan", "Subscriptions, net", "Transaction fees, net", "Net revenue", "Stripe costs", "HighLevel allocated*", "Other recorded", "Remaining*"].map((label) => <th key={label} scope="col" className="px-4 py-4 text-left font-bold">{label}</th>)}</tr></thead>
          <tbody>{rows.map((shop) => <Fragment key={shop.slug}><tr className="border-t border-slate-100 hover:bg-violet-50/40"><td className="px-4 py-4"><button
                  type="button"
                  aria-expanded={details === shop.slug}
                  aria-controls={`shop-details-${shop.slug}`}
                  onClick={() => setDetails((current) => current === shop.slug ? null : shop.slug)}
                  className="text-left font-bold text-violet-800 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet-700"
                >
                  <span className="block">{shop.name}</span>
                  <span className="mt-1 block text-xs font-semibold underline">
                    {details === shop.slug ? "Hide details" : "View details"}
                  </span>
                </button><p className="mt-1 text-xs text-slate-500">{shop.subscription_status.replaceAll("_", " ")} · {money(shop.current_monthly_cents)}/month</p></td><td className="px-4 py-4">{report.stripe_complete ? money(shop.subscription_collected_cents - shop.subscription_refunds_cents - shop.subscription_tax_cents) : "—"}</td><td className="px-4 py-4">{report.stripe_complete ? money(shop.transaction_fee_collected_cents - shop.transaction_fee_refunds_cents) : "—"}</td><td className="px-4 py-4 font-bold">{money(shop.revenue_cents)}</td><td className="px-4 py-4">{money(shop.stripe_cost_cents)}</td><td className="px-4 py-4">{money((shop.highlevel_live_cents || 0) + shop.highlevel_recorded_cents)}</td><td className="px-4 py-4">{money(shop.other_recorded_cents)}</td><td className={`px-4 py-4 font-bold ${shop.remaining_cents < 0 ? "text-red-700" : "text-violet-900"}`}>{money(shop.remaining_cents)}</td></tr>
              {details === shop.slug && <tr className="border-t border-violet-200 bg-violet-50/50">
                <td colSpan={8} className="px-4 py-5">
                  <section id={`shop-details-${shop.slug}`} aria-labelledby={`shop-details-title-${shop.slug}`}>
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <h3 id={`shop-details-title-${shop.slug}`} className="text-lg font-bold">{shop.name} · report details</h3>
                        <p className="mt-1 text-sm text-slate-600">Amounts for {report.month}. Shop service sales and customer refunds are excluded from ChairTime revenue.</p>
                      </div>
                      <button type="button" onClick={() => setDetails(null)} className="font-bold text-violet-700 hover:underline">Close details</button>
                    </div>
                    <dl className="mt-5 grid gap-x-6 gap-y-4 sm:grid-cols-3 xl:grid-cols-4">
                      {[
                        ["Subscription collections", shop.subscription_collected_cents],
                        ["Subscription refunds", shop.subscription_refunds_cents],
                        ["Subscription tax excluded", shop.subscription_tax_cents],
                        ["Platform fees collected", shop.transaction_fee_collected_cents],
                        ["Platform fee refunds", shop.transaction_fee_refunds_cents],
                        ["Subscription adjustments", shop.adjustments_cents],
                        ["ChairTime net revenue", shop.revenue_cents],
                        ["Stripe costs", shop.stripe_cost_cents],
                        ["HighLevel allocated wallet costs", shop.highlevel_live_cents],
                        ["HighLevel recorded costs", shop.highlevel_recorded_cents],
                        ["Other recorded costs", shop.other_recorded_cents],
                        ["Remaining after assigned costs", shop.remaining_cents],
                        ["Current plan list price per month", shop.current_monthly_cents],
                      ].map(([label, amount]) => <div key={label}>
                        <dt className="text-sm text-slate-600">{label}</dt>
                        <dd className="mt-1 font-bold">{money(amount)}</dd>
                      </div>)}
                    </dl>
                    {report.stripe_complete && shop.transaction_fee_collected_cents === 0 && shop.transaction_fee_refunds_cents === 0 && <p className="mt-4 text-sm text-slate-600">No ChairTime platform fee collections or refunds were recorded for this month. This does not establish whether a fee is configured for future payments.</p>}
                    <p className="mt-3 text-xs text-slate-500">HighLevel amounts include only allocated costs. Shared and unmatched usage appears in shared expenses; remaining amounts are provisional.</p>
                    <Link href={`/${shop.slug}/admin`} className="mt-4 inline-block text-sm font-bold text-violet-700">Open shop admin</Link>
                    <p className="mt-2 text-xs text-slate-500">Shop administration still requires that shop&apos;s own authorized login.</p>
                  </section>
                </td>
              </tr>}
            </Fragment>)}</tbody>
        </table>{!rows.length && <p className="p-6 text-slate-500">{loading ? "Loading shops…" : "No matching shops."}</p>}</div>
        <p className="border-t border-slate-200 px-5 py-3 text-xs text-slate-500">*HighLevel allocated costs exclude shared and unmatched usage. A $0 does not mean that a shop incurred no cost. Remaining amounts are provisional.</p>
      </section>

      {report?.highlevel && <section className="mt-7 rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
        <div className="flex flex-wrap justify-between gap-4"><div><h2 className="text-xl font-extrabold">HighLevel wallet usage</h2><p className="mt-1 text-sm text-slate-500">Actual billed charges in USD · ChairTime sub-account · {report.highlevel.transaction_count} transactions checked</p></div><div className="text-right"><p className="text-sm text-slate-500">Known wallet costs</p><p className="text-2xl font-extrabold">{money(report.highlevel.total_cents)}</p></div></div>
        <p className="mt-3 text-sm text-slate-600">{report.highlevel.status === "connected" ? "Phone number charges are assigned only when the number matches one shop. Voice AI, shared SMS and other usage remain shared or unassigned until their shop can be verified." : "A complete monthly lookup is required before live costs can be shown."}</p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{report.highlevel.categories.map((item) => <div key={item.category} className="flex justify-between gap-4 rounded-xl bg-slate-50 p-4"><span>{item.category}</span><strong>{money(item.amount_cents)}</strong></div>)}</div>
        <p className="mt-4 text-xs text-slate-500">{report.highlevel.complete ? "All returned transactions classified." : "Monthly costs are not fully verified."} Wallet funding transfers are excluded from service costs. Small usage charges are rounded after aggregation. HighLevel may post charges after the activity occurs.</p>
      </section>}
      <section className="mt-7 rounded-2xl border border-slate-200 bg-white p-5 sm:p-6"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-extrabold">Shared business expenses</h2><p className="mt-1 text-sm text-slate-500">HighLevel base plan, hosting, domains and other overhead.</p></div><button onClick={() => { setEntry(newEntry()); setShowEntry(true); setError(""); }} disabled={saving} className={buttonStyle}>Record an expense</button></div>
        <div className="mt-5 space-y-3">{report?.highlevel?.status === "connected" && <div className="flex justify-between gap-4 rounded-xl bg-violet-50 p-4"><div><p className="font-bold">HighLevel shared or unassigned wallet costs</p><p className="mt-1 text-xs text-slate-500">Automatically included · carrier fees, unmatched SMS, email and AI usage</p></div><p className="font-bold">{money(report.highlevel.shared_cents)}</p></div>}{report?.shared_expenses.length ? report.shared_expenses.map((expense) => <div key={expense.id} className="flex justify-between gap-4 rounded-xl bg-slate-50 p-4"><div><p className="font-bold">{expense.description}</p><p className="mt-1 text-xs text-slate-500">{providers[expense.provider]} · {expense.incurred_on} · {expense.reference}</p></div><p className="font-bold">{money(expense.amount_cents)}</p></div>) : <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-500">No shared expenses recorded for this month.</p>}</div>
        <div className="mt-5 flex justify-between border-t border-slate-200 pt-4 font-bold"><span>Shared expenses recorded</span><span>{money(totals.shared_expense_cents)}</span></div>
        <div className="mt-4 flex flex-wrap justify-between gap-3 rounded-xl bg-violet-100 p-5 text-lg font-extrabold text-violet-950"><span>Remaining after all recorded costs*</span><span>{money(remaining)}</span></div>
      </section>
      {showEntry && entry && <section className="mt-5 rounded-2xl border-2 border-violet-300 bg-white p-6"><h2 className="text-xl font-extrabold">Record a billed cost or credit</h2><p className="mt-2 text-sm text-slate-500">Enter each separate invoice line once. Choose HighLevel base plan for the agency subscription. When wallet costs are connected, manual HighLevel wallet entries are excluded to prevent double counting.</p><form onSubmit={saveExpense} className="mt-5 grid gap-4 sm:grid-cols-2">
        <label className="text-sm font-bold">Date incurred<input className={`${fieldStyle} mt-1`} type="date" required max={easternDate()} value={entry.incurred_on} onChange={(e) => setEntry({ ...entry, incurred_on: e.target.value })} disabled={saving} /></label>
        <label className="text-sm font-bold">Assign to<select className={`${fieldStyle} mt-1`} value={entry.shop_slug} onChange={(e) => setEntry({ ...entry, shop_slug: e.target.value })} disabled={saving}><option value="">Shared business expense</option>{report?.shops.map((shop) => <option key={shop.slug} value={shop.slug}>{shop.name}</option>)}</select></label>
        <label className="text-sm font-bold">Provider<select className={`${fieldStyle} mt-1`} value={entry.provider} onChange={(e) => setEntry({ ...entry, provider: e.target.value })} disabled={saving}>{Object.entries(providers).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
        <label className="text-sm font-bold">Entry type<select className={`${fieldStyle} mt-1`} value={entry.kind} onChange={(e) => setEntry({ ...entry, kind: e.target.value })} disabled={saving}><option value="cost">Cost</option><option value="credit">Credit / reimbursement</option></select></label>
        <label className="text-sm font-bold">Description<input className={`${fieldStyle} mt-1`} required maxLength={160} value={entry.description} onChange={(e) => setEntry({ ...entry, description: e.target.value })} placeholder="AI calls and phone usage" disabled={saving} /></label>
        <label className="text-sm font-bold">Unique invoice / transaction reference<input className={`${fieldStyle} mt-1`} required maxLength={120} value={entry.reference} onChange={(e) => setEntry({ ...entry, reference: e.target.value })} placeholder="Invoice-123/Gary" disabled={saving} /></label>
        <label className="text-sm font-bold">Amount (USD)<input className={`${fieldStyle} mt-1`} type="number" min="0.01" max="1000000" step="0.01" required value={entry.amount} onChange={(e) => setEntry({ ...entry, amount: e.target.value })} disabled={saving} /></label>
        <div className="flex items-end gap-3"><button disabled={saving} className={buttonStyle}>{saving ? "Saving…" : "Save expense"}</button><button type="button" disabled={saving} onClick={() => setShowEntry(false)} className="rounded-xl border border-slate-300 px-4 py-3 font-bold">Cancel</button></div>
      </form></section>}
      <details className="mt-6 rounded-2xl border border-slate-200 bg-white p-5"><summary className="cursor-pointer font-bold">Expense entries & audit history ({report?.expenses.length || 0})</summary><div className="mt-4 space-y-3">{report?.expenses.map((expense) => <div key={expense.id} className={`flex flex-wrap items-center justify-between gap-3 rounded-xl bg-slate-50 p-4 ${expense.is_void ? "opacity-50" : ""}`}><div><p className="font-bold">{expense.description} {expense.is_void && "(voided)"} {expense.excluded_from_totals && "(excluded from totals while wallet is connected)"}</p><p className="mt-1 text-xs text-slate-500">{expense.shop_slug || "Shared"} · {expense.incurred_on} · {expense.reference}</p></div><div className="flex items-center gap-4"><span className="font-bold">{money(expense.amount_cents)}</span>{!expense.is_void && <button disabled={saving} onClick={() => voidExpense(expense)} className="text-sm font-bold text-red-700">Void</button>}</div></div>)}</div></details>
      <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-5">
        <h2 className="text-lg font-bold">Recent outgoing texts</h2>
        <p className="mt-2 text-sm text-slate-600">Saved message IDs link future billed SMS charges to the sending shop. Accepted means HighLevel accepted the request; it does not confirm delivery or billing.</p>
        {report?.highlevel?.status === "connected" && <p className="mt-2 text-sm text-slate-600">Matched SMS charges this month: {report.highlevel.matched_sms_transactions ?? 0} · Unmatched: {report.highlevel.unmatched_sms_transactions ?? 0} · Matched Voice AI charges: {report.highlevel.matched_voice_transactions ?? 0} · Unmatched: {report.highlevel.unmatched_voice_transactions ?? 0} · Matched number rentals: {report.highlevel.matched_number_transactions ?? 0}</p>}
        <div className="mt-4 space-y-3">{report?.recent_outbound_messages?.length ? report.recent_outbound_messages.map((item) => <div key={item.attempt_id} className="rounded-xl bg-slate-50 p-3 text-sm"><p className="font-semibold">{item.shop_slug || "Unassigned"} · {item.purpose}</p><p className="mt-1 break-all text-slate-600">{item.status} · {item.created_at} · Message ID: {item.message_id || "Not recorded"}</p></div>) : <p className="text-sm text-slate-500">No tracked texts yet. Tracking begins after these changes are deployed.</p>}</div>
      </section>
      <footer className="mt-6 pb-6 text-xs leading-relaxed text-slate-500"><p>{report?.basis_note}</p><p className="mt-2">Active recurring plan total: {money(totals.active_monthly_cents)}/month. Trials are excluded from this recurring total. Subscription collections and transaction fees come from Stripe, not estimated plan amounts.</p></footer>
    </div>
  </main>;
}
