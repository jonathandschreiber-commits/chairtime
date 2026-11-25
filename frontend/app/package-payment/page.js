import Link from "next/link";

export default async function PackagePaymentPage({ searchParams }) {
  const { result, shop } = await searchParams;
  const bookingUrl = typeof shop === "string" && /^[a-z0-9-]+$/i.test(shop) ? `/${shop}` : null;
  return (
    <main className="mx-auto max-w-xl space-y-4 p-6">
      <h1 className="text-2xl font-bold">{result === "canceled" ? "Checkout canceled" : "Prepaid checkout"}</h1>
      <p>{result === "canceled"
        ? bookingUrl ? "You can return to the shop page to start checkout again." : "You can reopen the payment link from your text message."
        : "Your sessions are added to your account with the shop after Stripe confirms payment."}</p>
      {bookingUrl && <Link href={bookingUrl} className="text-indigo-700 underline">Return to the shop booking page</Link>}
    </main>
  );
}
