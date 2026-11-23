"use client";

import { ShopMessage } from "../../../../components/ShopLanguage";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

export default function CollectPaymentPage() {
  const { shop, appointmentId } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmRefund, setConfirmRefund] = useState(false);
  const [offerId, setOfferId] = useState("");
  const [packageNotice, setPackageNotice] = useState("");
  const pendingSale = useRef(null);
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

  async function packageAction(action, payload) {
    if (busy) return;
    if (action === "text-package-link") {
      const offer = data.package_offers.find(item => item.id === offerId);
      if (!offer) return;
      if (pendingSale.current?.offer_id !== offer.id) {
        pendingSale.current = { offer_id: offer.id, request_id: crypto.randomUUID() };
      }
      payload = pendingSale.current;
    }
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${endpoint}/${action}`, {
        method: "POST",
        headers: payload ? { "Content-Type": "application/json" } : undefined,
        body: payload ? JSON.stringify(payload) : undefined,
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Could not update the package.");
      if (action === "adjust-package") setPackageNotice("Package balance updated.");
      if (action === "text-package-link") {
        const notices = {
          sent: "Package payment link texted. Sessions are added after Stripe confirms payment.",
          paid: "Stripe confirmed payment. Package sessions are available.",
          expired: "This link expired. Select the package and send a new link.",
          sending: "This text is being sent.",
          unknown: "Text delivery could not be confirmed. Check with the customer before sending again.",
          pending: "Stripe is still processing the package payment.",
        };
        if (result.status === "failed") throw new Error("Could not text the package link. Try again.");
        setPackageNotice(notices[result.status] || "Check the package payment status.");
        if (["expired", "paid"].includes(result.status)) pendingSale.current = null;
      }
      await read();
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }

  return (
    <main className="mx-auto max-w-xl p-6">
      <Link className="text-blue-700 underline" href={`/${shop}/admin/calendar`}>Back to calendar</Link>
      <h1 className="mt-6 text-3xl font-bold"><ShopMessage>Payment details</ShopMessage></h1>
      {error && <p role="alert" className="mt-4 text-red-700">{error}</p>}
      {!data && !error && <p className="mt-4">Loading appointment…</p>}
      {data && <section className="mt-6 rounded-2xl border bg-white p-6">
        <p className="text-xl font-bold">{data.customer_name}</p>
        <p className="mt-2">{data.service_name} — ${data.amount}</p>
        {data.package_offers?.length > 0 && <div className="my-4 space-y-2 rounded-xl border p-4">
          <h2 className="font-bold">Prepaid packages</h2>
          {packageNotice && <p role="status">{packageNotice}</p>}
          <p>{data.package_sessions_remaining} eligible sessions remaining</p>
          <label className="block">Choose a package to sell
            <select className="block w-full rounded border p-2" value={offerId} onChange={event => setOfferId(event.target.value)}>
              <option value="">Choose package</option>
              {data.package_offers.map(offer => <option key={offer.id} value={offer.id}>
                {offer.name} · {offer.sessions} sessions · ${(offer.price_cents / 100).toFixed(2)}
              </option>)}
            </select>
          </label>
          <button type="button" disabled={busy || !offerId} className="rounded bg-indigo-700 px-3 py-2 text-white disabled:opacity-50" onClick={() => packageAction("text-package-link")}>Text package payment link</button>
        </div>}
        {data.adjustable_packages?.length > 0 && (
          <form className="my-4 space-y-3 rounded-xl border p-4" onSubmit={event => {
            event.preventDefault();
            const fields = new FormData(event.currentTarget);
            packageAction("adjust-package", {
              request_id: crypto.randomUUID(),
              sale_id: fields.get("purchase"),
              delta: Number(fields.get("change")),
              reason: fields.get("reason"),
            });
          }}>
            <h2 className="font-bold">Adjust package sessions</h2>
            <label className="block">Purchased package
              <select name="purchase" className="block w-full rounded border p-2" required>
                {data.adjustable_packages.map(purchase => (
                  <option key={purchase.id} value={purchase.id}>{purchase.name} · {purchase.remaining} remaining</option>
                ))}
              </select>
            </label>
            <label className="block">Sessions to add or deduct (use a minus sign to deduct)
              <input name="change" type="number" min={-1000} max={1000} step={1} className="block w-full rounded border p-2" required />
            </label>
            <label className="block">Reason
              <input name="reason" maxLength={300} className="block w-full rounded border p-2" required />
            </label>
            <button disabled={busy} className="rounded bg-indigo-700 px-3 py-2 text-white disabled:opacity-50">Save adjustment</button>
          </form>
        )}
        {data.package_paid ? <div className="mt-4 space-y-2">
          <p role="status" className="font-bold text-green-700">Paid with package</p>
          <button type="button" disabled={busy} className="underline" onClick={() => packageAction("reverse-package")}>Restore package session</button>
        </div> : data.payment_status === "paid" ? <p role="status" className="mt-5 font-bold text-green-700">Paid — ${data.amount}</p> :
          ["refunded", "partially_refunded", "refund_pending"].includes(data.payment_status) ? <div role="status" className="mt-5">
            <p className="font-bold">{data.payment_status === "refunded" ? "Refunded" : data.payment_status === "refund_pending" ? "Refund pending" : "Partially refunded"}</p>
            <p>Refunded to the original card: ${data.refunded_amount}</p>
            {data.payment_status === "refund_pending" && <p>Stripe has not confirmed completion. Refresh the status before taking another action.</p>}
          </div> : data.payment_status === "processing" ? <p className="mt-5">Payment is processing. Please check again before collecting another payment.</p> :
          <>
            {data.can_redeem_package && <button type="button" disabled={busy} className="mt-4 rounded-xl bg-green-700 px-4 py-3 font-bold text-white" onClick={() => packageAction("redeem-package")}>Complete checkout using 1 package session</button>}
            <p className="mt-5">Text a secure Stripe payment link to the customer’s saved phone number. They enter their card details on their own device.</p>
            <button type="button" disabled={busy || !!error || data.uses_tap_to_pay ||
              ["sent", "sending", "unknown"].includes(data.text_link_status) ||
              ["canceled", "no_show"].includes(data.appointment_status)} onClick={textLink}
              className="mt-4 rounded-xl bg-indigo-700 px-4 py-3 font-bold text-white disabled:opacity-50">
              {busy ? "Sending payment link…" : data.text_link_status === "sent" ? "Payment link texted" : "Text Payment Link to Customer"}
            </button>
            {data.text_link_status === "sent" && <p role="status" className="mt-3 text-green-700">Payment text accepted for the number ending {data.text_link_recipient}. Not paid yet.</p>}
            {["sending", "unknown"].includes(data.text_link_status) && <p role="status" className="mt-3">Text delivery is pending or unconfirmed. Check the customer’s messages before another send.</p>}
            {data.uses_tap_to_pay && <p className="mt-3">This payment was started in DayTello Counter. Resume it there to avoid a second charge.</p>}
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

