import Link from "next/link";

export const metadata = { title: "Support | DayTello" };

export default function Page() {
  return (
    <main className="mx-auto w-full max-w-3xl px-6 py-12">
      <Link href="/" className="font-semibold underline">DayTello home</Link>
      <h1 className="mt-8 text-4xl font-extrabold">Support</h1>
      <div className="mt-6 space-y-5 leading-relaxed">
        <p>Need help with setup, scheduling, your subscription, or a charge? Call <a className="underline" href="tel:+18887008909">888-700-8909</a>. If you reach voicemail, leave your shop name, a callback number, and a brief description.</p>
        <p>For questions about an appointment, contact the shop directly. If your confirmation includes a manage-booking link, use it to reschedule or cancel.</p>
        <p>DayTello is operated by PSI Meeting, Inc. The statement descriptor for DayTello subscription charges is DAYTELLO.</p>
      </div>
      <nav aria-label="DayTello information" className="mt-10 flex flex-wrap gap-4 border-t pt-6">
        <Link className="underline" href="/support">Support</Link>
        <Link className="underline" href="/privacy-policy">Privacy Policy</Link>
        <Link className="underline" href="/term-of-service">Terms of Service</Link>
      </nav>
    </main>
  );
}
