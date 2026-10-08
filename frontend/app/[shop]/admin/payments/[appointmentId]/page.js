"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

export default function CollectPaymentPage() {
  const { shop, appointmentId } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmRefund, setConfirmRefund] = useState(false);
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
    const timer = setInterval(read, 30000);
    window.addEventListener("focus", read);


  return () => { clearInterval(timer); window.removeEventListener("focus", read); };
  }, [data?.checkout_url, data?.payment_status, read]);

  async function textLink() {
    if (busy) return;
    setBusy(true); setError("");
    try {
      const response = await fetch(`${endpoint}/text-link`, { method: "POST" });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Could not send the payment link.");
      if (result.shop_slug !== shop) throw new Error("The payment did not match this shop.");
      setData(previous => ({ ...previous, ...result }));
    } catch (failure) { setError(failure.message || "Could not send the payment link."); }
    finally { setBusy(false); }
  }

  async function refundPayment() {
    if (busy) return;
    setBusy(true); setError("");
    try {
      const response = await fetch(`${endpoint}/refund`, { method: "POST" });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Could not confirm the refund. Refresh before trying again.");
      if (result.shop_slug !== shop) throw new Error("The payment did not match this shop.");
      setData(previous => ({ ...previous, ...result }));
      setConfirmRefund(false);
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }

  return (
    <main className="mx-auto max-w-xl p-6">
      <Link className="text-blue-700 underline" href={`/${shop}/admin/calendar`}>Back to calendar</Link>
      <h1 className="mt-6 text-3xl font-bold">Payment details</h1>
      {error && <p role="alert" className="mt-4 text-red-700">{error}</p>}
      {!data && !error && <p className="mt-4">Loading appointment…</p>}
      {data && <section className="mt-6 rounded-2xl border bg-white p-6">
        <p className="text-xl font-bold">{data.customer_name}</p>
        <p className="mt-2">{data.service_name} — ${data.amount}</p>
        {data.payment_status === "paid" ? <p role="status" className="mt-5 font-bold text-green-700">Paid — ${data.amount}</p> :
          ["refunded", "partially_refunded", "refund_pending"].includes(data.payment_status) ? <div role="status" className="mt-5">
            <p className="font-bold">{data.payment_status === "refunded" ? "Refunded" : data.payment_status === "refund_pending" ? "Refund pending" : "Partially refunded"}</p>
            <p>Refunded to the original card: ${data.refunded_amount}</p>
            {data.payment_status === "refund_pending" && <p>Stripe has not confirmed completion. Refresh the status before taking another action.</p>}
          </div> : data.payment_status === "processing" ? <p className="mt-5">Payment is processing. Please check again before collecting another payment.</p> :
          <>
            <p className="mt-5">Text a secure Stripe payment link to the customer’s saved phone number. They enter their card details on their own device.</p>
            <button type="button" disabled={busy || !!error || data.uses_tap_to_pay ||
              ["sent", "sending", "unknown"].includes(data.text_link_status) ||
              ["canceled", "no_show"].includes(data.appointment_status)} onClick={textLink}
              className="mt-4 rounded-xl bg-indigo-700 px-4 py-3 font-bold text-white disabled:opacity-50">
              {busy ? "Sending payment link…" : data.text_link_status === "sent" ? "Payment link texted" : "Text Payment Link to Customer"}
            </button>
            {data.text_link_status === "sent" && <p role="status" className="mt-3 text-green-700">Payment text accepted for the number ending {data.text_link_recipient}. Not paid yet.</p>}
            {["sending", "unknown"].includes(data.text_link_status) && <p role="status" className="mt-3">Text delivery is pending or unconfirmed. Check the customer’s messages before another send.</p>}
            {data.uses_tap_to_pay && <p className="mt-3">This payment was started in ChairTime Counter. Resume it there to avoid a second charge.</p>}
            <p className="mt-3 text-gray-600">This page updates to Paid after Stripe confirms payment.</p>
          </>}
        {data.refund_request_status && ["failed", "canceled"].includes(data.refund_request_status) && <p role="alert" className="mt-4 text-red-700">The refund did not complete. Check its details in Stripe before proceeding.</p>}
        {data.can_refund && !confirmRefund && <button type="button" disabled={busy || !!error} onClick={() => setConfirmRefund(true)} className="mt-5 rounded-xl border border-red-700 px-4 py-3 font-bold text-red-700 disabled:opacity-50">Refund payment</button>}
        {data.can_refund && confirmRefund && <div className="mt-5 rounded-xl border border-red-300 p-4">
          <p className="font-bold">Refund ${data.refundable_amount} to {data.customer_name}?</p>
          <p className="mt-2">The remaining payment goes back to the original card. This does not cancel the appointment. Stripe’s original processing fees are not returned.</p>
          <button type="button" disabled={busy || !!error} onClick={refundPayment} className="mt-4 rounded-xl bg-red-700 px-4 py-3 font-bold text-white disabled:opacity-50">{busy ? "Submitting refund…" : "Confirm refund"}</button>
          <button type="button" disabled={busy} onClick={() => setConfirmRefund(false)} className="ml-4 text-blue-700 underline">Keep payment</button>
        </div>}
        <button onClick={read} className="mt-5 block text-blue-700 underline">Refresh payment status</button>
      </section>}
    </main>
  );
}
