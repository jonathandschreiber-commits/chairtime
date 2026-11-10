import Link from "next/link";

export const metadata = { title: "Privacy Policy | DayTello" };

export default function Page() {
  return (
    <main className="mx-auto w-full max-w-3xl px-6 py-12">
      <Link href="/" className="font-semibold underline">DayTello home</Link>
      <h1 className="mt-8 text-4xl font-extrabold">Privacy Policy</h1>
      <div className="mt-6 space-y-5 leading-relaxed">
        <p>DayTello is operated by PSI Meeting, Inc. This policy describes information handled through the DayTello website and services.</p>
        <h2 className="text-xl font-semibold">Information we handle</h2>
        <p>DayTello handles account and contact details, shop settings, appointment information, and information you provide when asking for support. If a shop uses the AI receptionist or voicemail, call information may include phone numbers, call details, and voicemail recordings. Stripe processes subscription payments.</p>
        <h2 className="text-xl font-semibold">How we use information</h2>
        <p>We use this information to operate accounts, manage bookings, send appointment confirmations and reminders, provide phone features, handle billing, and respond to support requests. Service providers help deliver these features. Appointment information is available to the shop handling the booking.</p>
        <p>For questions about your information or to make a privacy request, contact <Link className="underline" href="/support">DayTello Support</Link>.</p>
      </div>
      <nav aria-label="DayTello information" className="mt-10 flex flex-wrap gap-4 border-t pt-6">
        <Link className="underline" href="/support">Support</Link>
        <Link className="underline" href="/privacy-policy">Privacy Policy</Link>
        <Link className="underline" href="/term-of-service">Terms of Service</Link>
      </nav>
    </main>
  );
}
