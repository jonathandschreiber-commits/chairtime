"use client";
import Link from "next/link";

export default function ServicePaymentButton({ appointment, user, shopSlug }) {
  const allowed = user?.role === "owner" ||
    (user?.role === "staff" && user?.can_accept_payments);
  if (!allowed || !appointment?.id || ["canceled", "no_show"].includes(appointment.status)) return null;
  return (
    <Link
      href={`/${encodeURIComponent(shopSlug)}/admin/payments/${encodeURIComponent(appointment.id)}`}
      className="inline-block rounded-xl bg-indigo-700 px-4 py-3 font-semibold text-white"
    >
      Collect payment
    </Link>
  );
}
