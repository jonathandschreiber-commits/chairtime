"use client";
import {useEffect, useRef, useState} from "react";
import {useParams} from "next/navigation";
import Link from "next/link";

function monday(value = new Date()) {
  const d = new Date(value.getFullYear(), value.getMonth(), value.getDate());
  d.setDate(d.getDate() - (d.getDay()+6)%7);
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
}
function addDays(value, days) {
  const d = new Date(value+"T12:00:00"); d.setDate(d.getDate()+days);
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
}
const hours = seconds => (seconds/3600).toFixed(2);
const money = value => new Intl.NumberFormat("en-US", {style:"currency", currency:"USD"}).format(value);
function totals(worker) {
  const hundredths = value => {
    if (!/^\d+(\.\d{0,2})?$/.test(String(value))) return 0n;
    const [whole, fraction = ""] = String(value).split(".");
    return BigInt(whole)*100n + BigInt(fraction.padEnd(2,"0"));
  };
  const paid = hundredths(worker.paid_hours), rate = hundredths(worker.hourly_rate);
  const numerator = (BigInt(worker.remaining_seconds)*100n + paid*3600n)*rate;
  const cents = (numerator+180000n)/360000n;
  return {payable:worker.remaining_seconds/3600 + Number(paid)/100,
    hourly:Number(cents)/100, total:Number(cents+hundredths(worker.commission))/100};
}
const clock = value => value.slice(11,16);
const inputClass = "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 disabled:bg-slate-100";
const buttonClass = "rounded-lg bg-indigo-600 px-4 py-2 font-semibold text-white disabled:opacity-50";

export default function TimesheetPage() {
  const params = useParams();
  const [legacyShop, setShop] = useState("");
  const shop = params.shop || legacyShop;
  const [startDate, setStartDate] = useState(monday());
  const [endDate, setEndDate] = useState(() => addDays(monday(),6));
  const rangeValid = startDate && endDate && endDate >= startDate &&
    new Date(endDate+"T00:00:00Z")-new Date(startDate+"T00:00:00Z") < 366*86400000;
  const query = `start_date=${startDate}&end_date=${endDate}`;
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [dirty, setDirty] = useState(false);
  const sequence = useRef(0);
  const approved = report?.status === "approved";
  useEffect(() => {
    if (params.shop) return;
    fetch("/api/auth/me", {cache:"no-store"}).then(r => r.json()).then(u => {
      if (u.shop_slug) setShop(u.shop_slug); else setError("Your login is not assigned to a shop.");
    }).catch(() => setError("Please sign in again."));
  }, [params.shop]);
  useEffect(() => {
    if (!shop) return;
    if (!rangeValid) {
      Promise.resolve().then(() => {setReport(null); setBusy(false); setError("Choose a start date and an end date, in order, covering 366 days or fewer.");});
      return;
    }
    const id = ++sequence.current;
    const controller = new AbortController();
    Promise.resolve().then(() => {
      if (controller.signal.aborted) return null;
      setBusy(true); setError(""); setNotice(""); setReport(null);
      return fetch(`/api/timesheets/${encodeURIComponent(shop)}?${query}`, {cache:"no-store", signal:controller.signal});
    })
      .then(async r => {if (!r) return null; const d = await r.json(); if (!r.ok) throw new Error(d.detail || "Could not load timesheet."); return d;})
      .then(d => {if (d && id === sequence.current) {setReport(d); setDirty(false);}})
      .catch(e => {if (e.name !== "AbortError" && id === sequence.current) setError(e.message);})
      .finally(() => {if (id === sequence.current) setBusy(false);});
    return () => controller.abort();
  }, [shop, query, rangeValid]);
  useEffect(() => {
    const prevent = e => {if (dirty) {e.preventDefault(); e.returnValue = "";}};
    window.addEventListener("beforeunload", prevent);
    return () => window.removeEventListener("beforeunload", prevent);
  }, [dirty]);
  function changeDate(field, value) {
    if (dirty && !window.confirm("Discard unsaved compensation entries and change the date range?")) return;
    sequence.current += 1;
    setReport(null); setDirty(false);
    if (field === "start") setStartDate(value); else setEndDate(value);
  }
  function edit(id, field, value) {
    setReport(r => ({...r, workers:r.workers.map(w => w.barber_id === id ? {...w, [field]:value} : w)}));
    setDirty(true); setNotice("");
  }
  async function save(approve = false, reopen = false) {
    if (reopen && !window.confirm("Reopen this approved period? Scheduled hours will be recalculated from current availability and blocked time.")) return;
    const invalid = report.workers.some(w => [[w.paid_hours,8784],[w.hourly_rate,10000],[w.commission,1000000]].some(([v,max]) =>
      v === "" || !/^\d+(\.\d{1,2})?$/.test(String(v)) || Number(v)>max));
    if (!reopen && invalid) {setError("Enter nonnegative amounts with up to two decimal places. Paid hours may not exceed 8,784."); return;}
    setBusy(true); setError(""); setNotice("");
    try {
      const payload = reopen ? {revision:report.revision} : {revision:report.revision, schedule_token:report.schedule_token, approve,
        workers:report.workers.map(w => ({barber_id:w.barber_id, paid_hours:w.paid_hours, hourly_rate:w.hourly_rate, commission:w.commission}))};
      const r = await fetch(`/api/timesheets/${encodeURIComponent(shop)}${reopen ? "/reopen" : ""}?${query}`,
        {method:reopen ? "POST" : "PUT", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)});
      const d = await r.json();
      if (!r.ok) throw new Error(typeof d.detail === "string" ? d.detail : "Check the compensation amounts and try again.");
      setReport(d); setDirty(false); setNotice(reopen ? "Period reopened." : approve ? "Period saved and approved." : "Draft saved.");
    } catch(e) {setError(e.message);} finally {setBusy(false);}
  }
  function exportCsv() {
    const cells = [["Start date","End date","Status","Worker","Timezone","Scheduled hours","Blocked hours","Hours after blocks","Owner approved paid hours","Payable hours","Hourly rate","Hourly compensation","Commission","Total compensation"]];
    for (const w of report.workers) cells.push([report.start_date, report.end_date, report.status, w.name, w.timezone,
      w.scheduled_hours,w.deducted_hours,w.remaining_hours,w.paid_hours,w.payable_hours,w.hourly_rate,w.hourly_compensation,w.commission,w.total_compensation]);
    cells.push([], ["Deduction detail"], ["Worker","Date","Start","End","Deducted hours","Reasons"]);
    for (const w of report.workers) for (const day of w.days) for (const d of day.deductions)
      cells.push([w.name,day.date,clock(d.start),clock(d.end),hours(d.seconds),d.reasons.join("; ")]);
    const escape = value => {let s = String(value ?? ""); if (/^\s*[=+@\-]/.test(s)) s = "'"+s; return '"'+s.replaceAll('"','""')+'"';};
    const url = URL.createObjectURL(new Blob(["\uFEFF"+cells.map(row => row.map(escape).join(",")).join("\r\n")], {type:"text/csv;charset=utf-8"}));
    const a = document.createElement("a"); a.href=url; a.download=`${shop}-timesheet-${startDate}-to-${endDate}.csv`; a.click(); URL.revokeObjectURL(url);
  }
  const sum = (key) => report?.workers.reduce((s,w) => s+totals(w)[key],0) || 0;
  return <main className="min-h-screen bg-slate-50 px-4 py-8 text-slate-900">
    <div className="mx-auto max-w-7xl">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div><h1 className="text-3xl font-bold">Time Sheet Report</h1><p className="mt-2 text-slate-600">Scheduled hours and owner-entered compensation for each worker.</p></div>
        <Link href={shop ? `/${shop}/admin` : "/admin"} onClick={e => {if (dirty && !window.confirm("Leave without saving your entries?")) e.preventDefault();}} className="rounded-lg border bg-white px-4 py-2">← Admin Home</Link>
      </div>
      <div className="mb-5 flex flex-wrap items-end gap-4 rounded-xl border bg-white p-5">
        <label className="font-semibold">Start date<input type="date" min="2020-01-01" max="2100-12-31" value={startDate} disabled={busy} onChange={e => changeDate("start",e.target.value)} className={`${inputClass} mt-2`} /></label>
        <label className="font-semibold">End date<input type="date" min={startDate || "2020-01-01"} max="2100-12-31" value={endDate} disabled={busy} onChange={e => changeDate("end",e.target.value)} className={`${inputClass} mt-2`} /></label>
        {report && <div><p className="font-semibold">{report.start_date} through {report.end_date}</p><p className="mt-2 text-sm">{approved ? "Approved — saved snapshot" : dirty ? "Draft — unsaved changes" : "Draft"}</p></div>}
        {report && <div className="ml-auto flex flex-wrap gap-2">
          {!approved ? <><button disabled={busy} onClick={() => save()} className={buttonClass}>Save Draft</button><button disabled={busy} onClick={() => save(true)} className={buttonClass}>Save and Approve</button></> :
            <button disabled={busy} onClick={() => save(false,true)} className={buttonClass}>Reopen Report</button>}
          <button disabled={busy || dirty || !report.revision} onClick={exportCsv} className="rounded-lg border px-4 py-2 disabled:opacity-50">Export CSV</button>
        </div>}
      </div>
      <p className="mb-5 text-sm text-slate-600">Hours come from staff availability, less staff blocks and shop closures within those hours. Overlapping blocks are deducted once. Hours use each worker’s local schedule. Drafts reflect current scheduling; approved periods keep their saved hours. This report records compensation and does not send payments.</p>
      {error && <p role="alert" className="mb-4 rounded-lg border border-red-200 bg-red-50 p-4 text-red-800">{error}</p>}
      {notice && <p role="status" className="mb-4 rounded-lg bg-emerald-50 p-4 text-emerald-800">{notice}</p>}
      {busy && <p role="status" className="mb-4">Loading or saving report…</p>}
      {report && <>
        <div className="mb-6 grid gap-4 sm:grid-cols-3">{[["Hourly compensation",sum("hourly")],["Commission",report.workers.reduce((s,w)=>s+Number(w.commission),0)],["Total compensation",sum("total")]].map(([label,value]) =>
          <div key={label} className="rounded-xl border bg-white p-5"><p className="text-slate-600">{label}</p><p className="mt-2 text-2xl font-bold">{money(value)}</p></div>)}</div>
        {!report.workers.length && <p className="rounded-xl border bg-white p-6">No workers are configured for this shop. Add staff in Staff &amp; Services.</p>}
        <div className="space-y-6">{report.workers.map(w => {const t = totals(w); return <section key={w.barber_id} className="rounded-xl border bg-white p-5">
          <h2 className="text-xl font-bold">{w.name}</h2><p className="mt-1 text-sm text-slate-500">{w.timezone}</p>
          <dl className="my-4 grid gap-4 sm:grid-cols-4">{[["Scheduled hours",w.scheduled_hours],["Blocked hours",w.deducted_hours],["Hours after blocks",w.remaining_hours],["Payable hours",t.payable.toFixed(2)]].map(([label,value]) => <div key={label}><dt className="text-sm text-slate-600">{label}</dt><dd className="mt-1 text-lg font-semibold">{value}</dd></div>)}</dl>
          <div className="grid gap-4 sm:grid-cols-3">
            {[["paid_hours","Owner-approved paid time (hours)",8784],["hourly_rate","Hourly pay ($)",10000],["commission","Commission ($)",1000000]].map(([field,label,max]) => <label key={field} className="font-medium">{label}<input type="number" min="0" max={max} step="0.01" value={w[field]} disabled={approved || busy} onChange={e=>edit(w.barber_id,field,e.target.value)} className={`${inputClass} mt-2`} /></label>)}
          </div>
          <p className="mt-2 text-sm text-slate-500">Owner-approved paid time adds hours back to the hours after blocks. For example, enter 5 to pay five hours of otherwise deducted time.</p>
          <div className="mt-4 flex flex-wrap gap-x-8 gap-y-2 rounded-lg bg-indigo-50 p-4"><p>Hourly compensation: <strong>{money(t.hourly)}</strong></p><p>Commission: <strong>{money(w.commission)}</strong></p><p>Total: <strong>{money(t.total)}</strong></p></div>
          <details className="mt-5"><summary className="cursor-pointer font-semibold">Daily hours and deduction reasons</summary><div className="mt-3 overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b"><th className="p-2">Date</th><th className="p-2">Scheduled</th><th className="p-2">Deducted</th><th className="p-2">After blocks</th><th className="p-2">Deduction details</th></tr></thead><tbody>{w.days.map(day => <tr key={day.date} className="border-b align-top"><td className="p-2 whitespace-nowrap">{day.date}</td><td className="p-2">{hours(day.scheduled_seconds)}</td><td className="p-2">{hours(day.deducted_seconds)}</td><td className="p-2">{hours(day.remaining_seconds)}</td><td className="p-2">{day.deductions.length ? day.deductions.map((d,i)=><p key={i} className="mb-1">{clock(d.start)}–{clock(d.end)} ({hours(d.seconds)} hours): {d.reasons.join("; ")}</p>) : "No deductions"}</td></tr>)}</tbody></table></div></details>
        </section>;})}</div>
        <p className="mt-5 text-sm text-slate-500">Compensation is calculated from unrounded scheduled duration and rounded to cents per worker. Save before exporting. Hourly rates carry forward from the most recent saved earlier period; paid-time adjustments and commissions start at zero for a new date range.</p>
      </>}
    </div>
  </main>;
}
