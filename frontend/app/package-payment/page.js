export default async function PackagePaymentPage({ searchParams }) {
  const { result } = await searchParams;
  return (
    <main className="mx-auto max-w-xl space-y-4 p-6">
      <h1 className="text-2xl font-bold">{result === "canceled" ? "Checkout canceled" : "Package checkout"}</h1>
      <p>{result === "canceled"
        ? "You can reopen the payment link from your text message."
        : "Your sessions are added to your account with the shop after Stripe confirms payment."}</p>
    </main>
  );
}
