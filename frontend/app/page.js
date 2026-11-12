import Link from "next/link";

const primaryButton = "inline-flex items-center justify-center rounded-2xl bg-[#321275] font-bold text-white shadow-sm transition-colors hover:bg-[#250b5b] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#321275]";
const secondaryButton = "inline-flex items-center justify-center rounded-2xl bg-[#00666b] font-bold text-white shadow-sm transition-colors hover:bg-[#004d51] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#00666b]";

export default function HomePage() {
  return (
    <main className="min-h-screen bg-white text-[#161431]">
      <header className="border-b border-[#e7dff4]">
        <div className="max-w-6xl mx-auto px-6 py-3 flex items-center justify-end">
          <Link
            href="/login"
            className={`${secondaryButton} shrink-0 px-5 py-2.5`}
          >
            Sign In
          </Link>
        </div>
      </header>

      <section className="bg-linear-to-br from-[#f4edff] via-[#faf7ff] to-[#e1f6f3]">
        <div className="max-w-6xl mx-auto px-6 py-20 sm:py-28">
          <div className="max-w-4xl">
            <p className="mb-4 text-lg font-bold text-[#00666b]">
              Simple scheduling for busy businesses
            </p>

            <h1 className="text-5xl sm:text-7xl font-extrabold tracking-tight leading-tight">
              Run your shop.
              <br />
              <span className="text-[#321275]">We&apos;ll handle the scheduling.</span>
            </h1>

            <p className="mt-7 text-xl sm:text-2xl leading-relaxed text-gray-700 max-w-3xl">
              DayTello keeps appointments, customers, reminders,
              and booking in one simple place — so you can spend less
              time managing the schedule and more time with your customers.
            </p>

            <div className="mt-10 flex flex-col sm:flex-row gap-4">
              <Link
                href="/signup"
                className={`${primaryButton} px-8 py-5 text-xl`}
              >
                Start My Free Month
              </Link>

              <Link
                href="/login"
                className={`${secondaryButton} px-8 py-5 text-xl`}
              >
                I Already Have an Account
              </Link>
            </div>

            <p className="mt-4 text-gray-600 font-medium">
              Free for 30 days. No charge today. Cancel anytime.
            </p>
          </div>
        </div>
      </section>

      <section className="max-w-6xl mx-auto px-6 py-20">
        <div className="text-center max-w-3xl mx-auto">
          <h2 className="text-4xl sm:text-5xl font-extrabold tracking-tight">
            Never miss a customer because you&apos;re too busy to answer the phone.
          </h2>

          <p className="mt-6 text-xl text-gray-700 leading-relaxed">
            You&apos;re working with a customer. The phone rings.
            Instead of stopping what you&apos;re doing — or losing the
            appointment — DayTello lets customers book online or by phone.
            Their appointment goes directly onto your schedule.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-6 mt-14">
          <div className="rounded-3xl border border-[#e7dff4] bg-[#faf7ff] p-8">
            <div aria-hidden="true" className="mb-4 grid size-12 place-items-center rounded-xl bg-[#d9f2ee] text-2xl text-[#00666b]">☎️</div>

            <h3 className="text-2xl font-extrabold">
              Never miss a booking
            </h3>

            <p className="mt-3 text-lg text-gray-700 leading-relaxed">
              Customers can book even when you&apos;re busy, with another
              customer, or unable to answer the phone.
            </p>
          </div>

          <div className="rounded-3xl border border-[#e7dff4] bg-[#faf7ff] p-8">
            <div aria-hidden="true" className="mb-4 grid size-12 place-items-center rounded-xl bg-[#d9f2ee] text-2xl text-[#00666b]">📅</div>

            <h3 className="text-2xl font-extrabold">
              Keep everything organized
            </h3>

            <p className="mt-3 text-lg text-gray-700 leading-relaxed">
              Your appointments, customer information, notes, schedules,
              confirmations, and reminders stay together.
            </p>
          </div>

          <div className="rounded-3xl border border-[#e7dff4] bg-[#faf7ff] p-8">
            <div aria-hidden="true" className="mb-4 grid size-12 place-items-center rounded-xl bg-[#d9f2ee] text-2xl text-[#00666b]">✓</div>

            <h3 className="text-2xl font-extrabold">
              Keep it simple
            </h3>

            <p className="mt-3 text-lg text-gray-700 leading-relaxed">
              DayTello is designed to be easy for owners, staff,
              and customers without complicated software to learn.
            </p>
          </div>
        </div>
      </section>

      <section className="bg-linear-to-br from-[#24104d] to-[#302369] text-white">
        <div className="max-w-6xl mx-auto px-6 py-20">
          <div className="grid md:grid-cols-2 gap-14">
            <div>
              <p className="font-bold text-[#a8eee4] mb-3">
                FOR YOUR BUSINESS
              </p>

              <h2 className="text-4xl font-extrabold tracking-tight">
                Less scheduling work.
                <br />
                More time for customers.
              </h2>

              <div className="mt-8 space-y-5 text-xl">
                <p>✓ See today&apos;s schedule at a glance.</p>
                <p>✓ Keep customer history and notes organized.</p>
                <p>✓ Move or cancel appointments quickly.</p>
                <p>✓ Send confirmations and reminders automatically.</p>
                <p>✓ Let customers book without interrupting your day.</p>
              </div>
            </div>

            <div>
              <p className="font-bold text-[#a8eee4] mb-3">
                FOR YOUR CUSTOMERS
              </p>

              <h2 className="text-4xl font-extrabold tracking-tight">
                Booking should be easy for them, too.
              </h2>

              <div className="mt-8 space-y-5 text-xl">
                <p>✓ Book when it&apos;s convenient.</p>
                <p>✓ Book online or by phone.</p>
                <p>✓ Choose from available appointment times.</p>
                <p>✓ Receive automatic confirmation texts.</p>
                <p>✓ Receive reminders before appointments.</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="bg-[#eaf8f6] px-6 py-20 text-center">
        <h2 className="text-4xl sm:text-5xl font-extrabold tracking-tight">
          Set up your shop in minutes.
        </h2>

        <p className="mt-5 text-xl text-gray-700 max-w-2xl mx-auto">
          Add your staff, services, and hours. DayTello gives your
          business its own booking page and keeps everything organized
          from there.
        </p>

        <Link
          href="/signup"
          className={`${primaryButton} mt-9 px-10 py-5 text-xl`}
        >
          Start My Free Month
        </Link>

        <p className="mt-4 text-gray-600">
          Free for 30 days. No charge today.
        </p>
      </section>

      <footer className="border-t border-[#e7dff4]">
        <div className="max-w-6xl mx-auto px-6 py-8 flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between text-gray-600">
          <p>© 2026 DayTello</p>

          <Link href="/login" className={`${secondaryButton} px-5 py-2.5`}>
            Shop Owner Sign In
          </Link>
        </div>
      </footer>
    </main>
  );
}
