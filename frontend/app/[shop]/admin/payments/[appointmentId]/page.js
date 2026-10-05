"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

export default function CollectPaymentPage() {
  const { shop, appointmentId } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const endpoint = `/api/payments/appointments/${encodeURIComponent(appointmentId)}`;

  const read = useCallback(async () => {
    try {
      const response = await fetch(endpoint, { cache: "no-store" });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Could not check payment.");
      if (result.shop_slug !== shop) throw new Error("Please sign in to this shop's account.");
      setData(result);
      setError("");
    } catch (failure) { setError(failure.message || "Could not check payment."); }
  }, [endpoint, shop]);

  useEffect(() => { read(); }, [read]);
  useEffect(() => {
    if (!data?.checkout_url && data?.payment_status !== "processing") return;
    const timer = setInterval(read, 15000);
    window.addEventListener("focus", read);
    return () => { clearInterval(timer); window.removeEventListener("focus", read); };
  }, [data?.checkout_url, data?.payment_status, read]);

  async function createLink() {
    if (busy) return;
    setBusy(true); setError("");
    try {
      const response = await fetch(`${endpoint}/checkout`, { method: "POST" });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Could not create checkout.");
      if (result.shop_slug !== shop) throw new Error("The payment did not match this shop.");
      setData(previous => ({ ...previous, ...result }));
    } catch (failure) { setError(failure.message || "Could not create checkout."); }
    finally { setBusy(false); }
  }

  async function copyLink() {
    try { await navigator.clipboard.writeText(data.checkout_url); setCopied(true); }
    catch { setError("Could not copy. Select and copy the payment link below."); }
  }

  return (
    <main className="mx-auto max-w-xl p-6">
      <Link className="text-blue-700 underline" href={`/${shop}/admin/calendar`}>Back to calendar</Link>
      <h1 className="mt-6 text-3xl font-bold">Collect payment</h1>
      {error && <p role="alert" className="mt-4 text-red-700">{error}</p>}
      {!data && !error && <p className="mt-4">Loading appointment…</p>}
      {data && <section className="mt-6 rounded-2xl border bg-white p-6">
        <p className="text-xl font-bold">{data.customer_name}</p>
        <p className="mt-2">{data.service_name} — ${data.amount}</p>
        {data.payment_status === "paid" ? <p role="status" className="mt-5 font-bold text-green-700">Paid — ${data.amount}</p> :
          data.payment_status === "processing" ? <p className="mt-5">Payment is processing. Please check again before collecting another payment.</p> :
          data.checkout_url ? <>
            <p className="mt-5">The customer pays on Stripe’s secure checkout. Copy the link to share it, or open it on the customer’s device.</p>
            <div className="mt-4 flex flex-wrap gap-3">
              <button onClick={copyLink} className="rounded-xl bg-indigo-700 px-4 py-3 font-bold text-white">{copied ? "Link copied" : "Copy payment link"}</button>
              <a href={data.checkout_url} target="_blank" rel="noopener noreferrer" className="rounded-xl border px-4 py-3 font-bold">Open checkout</a>
            </div>
            <input aria-label="Payment link" readOnly value={data.checkout_url} className="mt-4 w-full rounded-lg border p-3" onFocus={event => event.target.select()} />
            <p className="mt-3 text-gray-600">Not paid yet. This page updates after Stripe confirms payment.</p>
          </> : <>
            <p className="mt-5">Create a secure payment link for this service. The customer confirms the charge on Stripe.</p>
            <button disabled={busy || !!error || ["canceled", "no_show"].includes(data.appointment_status)} onClick={createLink} className="mt-4 rounded-xl bg-indigo-700 px-4 py-3 font-bold text-white disabled:opacity-50">{busy ? "Creating link…" : `Create payment link — $${data.amount}`}</button>
          </>}
        <button onClick={read} className="mt-5 block text-blue-700 underline">Refresh payment status</button>
      </section>}
    </main>
  );
}
