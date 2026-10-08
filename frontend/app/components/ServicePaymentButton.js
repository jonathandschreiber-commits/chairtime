"use client";
import Link from "next/link";
import { useEffect, useState } from "react";

export default function ServicePaymentButton({ appointment, user, shopSlug }) {
  const allowed = user?.role === "owner" ||
    (user?.role === "staff" && user?.can_accept_payments);
  const appointmentId = appointment?.id;
  const visible = allowed && user?.shop_slug === shopSlug && appointmentId &&
    !["canceled", "no_show"].includes(appointment.status);
  const [payment, setPayment] = useState(null);
  const identity = `${user?.id}:${shopSlug}:${appointmentId}`;

  useEffect(() => {
    if (!visible) return;
    let active = true;
    let controller;
    async function refresh() {
      if (document.visibilityState === "hidden") return;
      controller?.abort();
      controller = new AbortController();
      const current = controller;
      try {
        const response = await fetch(
          `/api/payments/appointments/${encodeURIComponent(appointmentId)}`,
          { cache: "no-store", signal: current.signal }
        );
        const data = await response.json();
        if (!response.ok || data.success !== true ||
            data.shop_slug !== shopSlug || data.appointment_id !== appointmentId) {
          throw new Error("Payment status could not be verified.");
        }
        if (active && !current.signal.aborted) {
          setPayment({ identity, data });
        }
      } catch {
        if (active && !current.signal.aborted) {
          setPayment({ identity, data: null });
        }
      }
    }
    refresh();
    const interval = window.setInterval(refresh, 30000);
    window.addEventListener("focus", refresh);
    window.addEventListener("pageshow", refresh);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      active = false;
      controller?.abort();
      window.clearInterval(interval);
      window.removeEventListener("focus", refresh);
      window.removeEventListener("pageshow", refresh);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [visible, identity, appointmentId, shopSlug]);

  if (!visible) return null;
  const current = payment?.identity === identity ? payment : null;
  const data = current?.data;
  const paid = data?.payment_status === "paid";
  const amount = Number(data?.amount);
  const validAmount = data?.amount != null && Number.isFinite(amount) && amount >= 0;
  const currency = String(data?.currency || "usd").toUpperCase();
  const formattedAmount = validAmount && /^[A-Z]{3}$/.test(currency)
    ? new Intl.NumberFormat("en-US", { style: "currency", currency }).format(amount)
    : null;
  function formatRefundAmount(value) {
    const number = Number(value);
    if (value == null || !Number.isFinite(number) || number < 0 ||
        !/^[A-Z]{3}$/.test(currency)) return null;
    return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(number);
  }
  const refundedAmount = formatRefundAmount(data?.refunded_amount);
  const labels = {
    paid: `Paid${formattedAmount ? ` — ${formattedAmount}` : ""}`,
    refunded: `Refunded${refundedAmount ? ` — ${refundedAmount}` : ""}`,
    partially_refunded: `Partially refunded${refundedAmount && formattedAmount
      ? ` — ${refundedAmount} of ${formattedAmount}` : ""}`,
    refund_pending: "Refund pending",
    processing: "Payment processing",
    unpaid: "Collect payment",
    expired: "Collect payment",
    canceled: "Card payment canceled",
  };
  const label = labels[data?.payment_status] ||
    (current ? "Payment status unavailable — view details" : "Checking payment…");
  return (
    <Link
      href={`/${encodeURIComponent(shopSlug)}/admin/payments/${encodeURIComponent(appointment.id)}`}
      className={`inline-block rounded-xl px-4 py-3 font-semibold ${
        paid ? "bg-green-100 text-green-800" : "bg-indigo-700 text-white"
      }`}
    >
      {label}
    </Link>
  );
}
