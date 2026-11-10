import Image from "next/image";
import Link from "next/link";

export const metadata = { title: "Terms of Service | DayTello" };

export default function Page() {
  return (
    <main className="mx-auto w-full max-w-3xl px-6 py-12">
      <Link href="/" className="inline-block" aria-label="DayTello home">
        <Image src="/daytello-logo.png" alt="DayTello" width={350} height={180} className="h-auto w-56 max-w-full sm:w-80" unoptimized />
      </Link>
      <h1 className="mt-8 text-4xl font-extrabold">Terms of Service</h1>
      <div className="mt-6 space-y-5 leading-relaxed">
        <p>DayTello is operated by PSI Meeting, Inc. These terms cover use of DayTello scheduling and related services.</p>
        <h2 className="text-xl font-semibold">Using DayTello</h2>
        <p>Keep your account credentials secure and your shop’s services, hours, and prices accurate. Use the service lawfully and only submit information you are authorized to share.</p>
        <h2 className="text-xl font-semibold">Subscriptions and billing</h2>
        <p>Your checkout shows the selected plan, price, billing interval, and any trial. Paid subscriptions renew at the displayed interval unless canceled. If your plan includes a trial, check the first billing date shown at checkout. For help with cancellation or a billing question, contact <Link className="underline" href="/support">DayTello Support</Link>.</p>
        <p>Appointments booked through DayTello are provided by the shop. Contact the shop for questions about its services, appointment changes, or charges for an appointment.</p>
      </div>
      <nav aria-label="DayTello information" className="mt-10 flex flex-wrap gap-4 border-t pt-6">
        <Link className="underline" href="/support">Support</Link>
        <Link className="underline" href="/privacy-policy">Privacy Policy</Link>
        <Link className="underline" href="/term-of-service">Terms of Service</Link>
      </nav>
    </main>
  );
}
