"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

export default function PaymentReceiptPage() {
  const { shop } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    const token = new URL(window.location.href).searchParams.get("token") || "";
    const query = new URLSearchParams({ token, shop_slug: shop });
    async function read() {
      try {
        const response = await fetch(`/api/payments/receipt?${query}`, { cache: "no-store" });
        const result = await response.json();
        if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Could not verify payment.");
        if (active) { setData(result); setError(""); }
      } catch (failure) { if (active) setError(failure.message || "Could not verify payment."); }
    }
    read();
    return () => { active = false; };
  }, [shop, revision]);
  useEffect(() => {
    if (data?.payment_status !== "processing") return;
    const timer = setTimeout(() => setRevision(v => v + 1), 5000);
    return () => clearTimeout(timer);
  }, [data, revision]);
  return <main className="mx-auto max-w-xl p-6">
    <h1 className="text-3xl font-bold">{data?.shop_name || "Service payment"}</h1>
    {error ? <p role="alert" className="mt-5 text-red-700">{error}</p> : !data ? <p className="mt-5">Checking payment…</p> : <section className="mt-6 rounded-2xl border p-6">
      <p>{data.service_name} — ${data.amount}</p>
      {data.payment_status === "paid" ? <p role="status" className="mt-4 text-xl font-bold text-green-700">Payment confirmed. Thank you!</p> : <>
        <p className="mt-4">{data.payment_status === "processing" ? "Your payment is processing. Please wait for confirmation." : "Payment has not been completed."}</p>
        {data.checkout_url && <a className="mt-4 inline-block rounded-xl bg-indigo-700 px-4 py-3 font-bold text-white" href={data.checkout_url}>Return to checkout</a>}
      </>}
    </section>}
    <button className="mt-5 block text-blue-700 underline" onClick={() => setRevision(v => v + 1)}>Check payment status</button>
    <Link className="mt-5 block text-blue-700 underline" href={`/${shop}`}>Back to booking page</Link>
  </main>;
}
