"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

export default function CollectPaymentPage() {
  const { shop, appointmentId } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
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
    if (data?.payment_status === "paid") return;
    const timer = setInterval(read, 15000);
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
        <button onClick={read} className="mt-5 block text-blue-700 underline">Refresh payment status</button>
      </section>}
    </main>
  );
}
