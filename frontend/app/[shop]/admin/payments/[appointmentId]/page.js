"use client";

import PackageBalances from "../../../../components/PackageBalances";

import { ShopMessage } from "../../../../components/ShopLanguage";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

const offlineMethods = {
  cash: "Cash", check: "Check", external_card: "External card terminal",
  bank_transfer: "Bank transfer", other: "Other",
};

export default function CollectPaymentPage() {
  const { shop, appointmentId } = useParams();
  const router = useRouter();
  const [completion, setCompletion] = useState(null);
  const [paymentMethod, setPaymentMethod] = useState("");
  const [confirmedPayment, setConfirmedPayment] = useState(false);
  const [note, setNote] = useState("");
  const [noNotes, setNoNotes] = useState(false);
  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    if (query.get("complete") === "1") {
      const from = query.get("from");
      setCompletion(["customers", "today", "calendar"].includes(from) ? from : "calendar");
    }
  }, []);
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

  async function submitCompletion(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${endpoint}/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          method: data.package_paid ? "package" : data.payment_status === "paid" ? "stripe" : paymentMethod,
          note: noNotes ? "" : note,
          no_notes: noNotes,
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Could not complete appointment.");
      router.push(`/${shop}/admin/${completion}`);
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }

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
      if (action === "package-expiration") setPackageNotice("Expiration date saved.");
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

  if (completion) {
    const paid = data?.payment_status === "paid" || data?.package_paid;
    const ready = paid || confirmedPayment;
    const checkoutDescription = data?.package_paid ? "Paid with a prepaid session." : data?.payment_status === "paid" ? "Payment received · Stripe confirmed." :
      paymentMethod === "package" ? "One eligible prepaid session will be used on submission." : "Payment received outside Stripe.";
    return (
      <main className="mx-auto max-w-lg space-y-4 px-5 py-8">
        <Link href={`/${shop}/admin/${completion}`} className="text-blue-700 underline">Back to appointments</Link>
        <h1 className="text-3xl font-bold">Complete appointment</h1>
        {error && <p role="alert" className="text-red-700">{error}</p>}
        {data && <section className="space-y-4 rounded-xl border bg-white p-5">
          <p className="font-semibold">{data.customer_name} · {data.service_name} · ${data.amount}</p>
          {data.appointment_status === "completed" ? <p>This appointment is already completed.</p> : <>
            {!paid && <label className="block font-semibold">Payment method
              <select className="mt-2 block w-full rounded border p-2" value={paymentMethod}
                onChange={event => { setPaymentMethod(event.target.value); setConfirmedPayment(false); }}>
                <option value="">Choose payment method</option>
                <option value="stripe">Stripe</option>
                {data.can_redeem_package && <option value="package">Use one prepaid session ({data.package_sessions_remaining} available)</option>}
                {Object.entries(offlineMethods).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
              </select>
            </label>}
            {!paid && paymentMethod === "stripe" && <div className="space-y-2">
              {data.text_link_status === "sent" || data.uses_tap_to_pay ? <p>Awaiting Stripe confirmation.</p> :
                <button type="button" disabled={busy || ["sending", "unknown"].includes(data.text_link_status)}
                  onClick={textLink} className="rounded bg-indigo-700 px-3 py-2 text-white disabled:opacity-50">Text Stripe payment link</button>}
              <button type="button" onClick={read} className="block text-blue-700 underline">Check payment status</button>
            </div>}
            {!paid && paymentMethod && paymentMethod !== "stripe" && !confirmedPayment &&
              <button type="button" onClick={() => setConfirmedPayment(true)} className="rounded bg-indigo-700 px-3 py-2 text-white">
                {paymentMethod === "package" ? "Confirm prepaid session" : "Confirm payment received"}
              </button>}
            {ready && <form onSubmit={submitCompletion} className="space-y-3">
              <p role="status">{checkoutDescription}</p>
              <label className="block font-semibold">Appointment notes
                <textarea className="mt-1 block w-full rounded border p-2" rows={3} maxLength={2000}
                  required={!noNotes} disabled={noNotes} value={note} onChange={event => setNote(event.target.value)} />
              </label>
              <label className="flex gap-2"><input type="checkbox" checked={noNotes}
                onChange={event => setNoNotes(event.target.checked)} /> None</label>
              <button disabled={busy || (!noNotes && !note.trim())} className="rounded bg-green-700 px-4 py-2 font-bold text-white disabled:opacity-50">
                Submit and complete
              </button>
            </form>}
          </>}
        </section>}
      </main>
    );
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
        {(data.package_offers?.length > 0 || data.package_sessions_remaining > 0 || data.package_balances?.length > 0) && <div className="my-4 space-y-2 rounded-xl border p-4">
          <h2 className="font-bold">Prepaid packages</h2>
          {packageNotice && <p role="status">{packageNotice}</p>}
          <PackageBalances payment={data} />
          {data.can_edit_package_expiration && data.package_balances?.filter(purchase =>
            !purchase.expired && purchase.sessions_remaining > 0
          ).map(purchase => (
            <details key={purchase.id} className="rounded-lg border p-3">
              <summary className="cursor-pointer font-medium">
                Edit expiration for purchase {new Date(purchase.purchased_at).toLocaleDateString()}
              </summary>
              <form className="mt-2 flex flex-wrap items-end gap-2" onSubmit={event => {
                event.preventDefault();
                const fields = new FormData(event.currentTarget);
                packageAction("package-expiration", {
                  purchase_id: purchase.id,
                  expiration_date: fields.get("expiration"),
                });
              }}>
                <label>Last day to use
                  <input type="date" name="expiration" required defaultValue={purchase.expiration_date ?? ""}
                    key={purchase.expiration_date ?? "unset"} className="block rounded border p-2" />
                </label>
                <button disabled={busy} className="rounded bg-indigo-700 px-3 py-2 text-white disabled:opacity-50">
                  Save expiration
                </button>
              </form>
            </details>
          ))}

          {data.package_offers?.length > 0 && <>
          <label className="block">Choose a package to sell
            <select className="block w-full rounded border p-2" value={offerId} onChange={event => setOfferId(event.target.value)}>
              <option value="">Choose package</option>
              {data.package_offers.map(offer => <option key={offer.id} value={offer.id}>
                {offer.name} · {offer.sessions} sessions · ${(offer.price_cents / 100).toFixed(2)}
              </option>)}
            </select>
          </label>
          <button type="button" disabled={busy || !offerId} className="rounded bg-indigo-700 px-3 py-2 text-white disabled:opacity-50" onClick={() => packageAction("text-package-link")}>Text package payment link</button>
          </>}
        </div>}
        {data.manual_payment_method ? <p role="status" className="mt-4 font-bold text-green-700">Paid · {offlineMethods[data.manual_payment_method]}</p> : data.package_paid ? <div className="mt-4 space-y-2">
          <p role="status" className="font-bold text-green-700">Paid with package</p>
          <Link href={`/${shop}/admin/retail`} className="text-indigo-700 underline">Sell another service or package</Link>
        </div> : data.payment_status === "paid" ? <p role="status" className="mt-5 font-bold text-green-700">Payment received — ${data.amount}</p> :
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

