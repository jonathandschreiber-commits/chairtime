import Link from "next/link";

export default async function AIUsagePage({ params }) {
  const { shop } = await params;

  return (
    <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <Link href={`/${encodeURIComponent(shop)}/admin`} className="text-sm font-semibold text-indigo-700">
        Back to dashboard
      </Link>
      <section className="mt-4 rounded-2xl border border-indigo-100 bg-white p-6 shadow-sm">
        <h1 className="text-2xl font-bold text-slate-900">AI Usage &amp; Billing</h1>
        <p className="mt-2 text-sm text-slate-700">
          Usage reporting is being set up. Your AI minutes and usage charges aren’t available here yet.
        </p>
      </section>
    </main>
  );
}
