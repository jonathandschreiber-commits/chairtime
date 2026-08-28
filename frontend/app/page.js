import Link from "next/link";

export default function HomePage() {
  return (
    <main className="min-h-screen bg-white text-gray-950">
      <header className="border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-6 py-5 flex items-center justify-between">
          <div className="text-2xl font-extrabold tracking-tight">
            ChairTime
          </div>

          <Link
            href="/login"
            className="font-bold hover:underline"
          >
            Sign In
          </Link>
        </div>
      </header>

      <section className="bg-gray-50">
        <div className="max-w-6xl mx-auto px-6 py-20 sm:py-28">
          <div className="max-w-4xl">
            <p className="font-bold text-lg mb-4">
              Simple scheduling for busy businesses
            </p>

            <h1 className="text-5xl sm:text-7xl font-extrabold tracking-tight leading-tight">
              Run your shop.
              <br />
              We&apos;ll handle the scheduling.
            </h1>

            <p className="mt-7 text-xl sm:text-2xl leading-relaxed text-gray-700 max-w-3xl">
              ChairTime keeps appointments, customers, reminders,
              and booking in one simple place — so you can spend less
              time managing the schedule and more time with your customers.
            </p>

            <div className="mt-10 flex flex-col sm:flex-row gap-4">
              <Link
                href="/signup"
                className="inline-flex justify-center items-center bg-black text-white rounded-2xl px-8 py-5 text-xl font-bold"
              >
                Start My Free Month
              </Link>

              <Link
                href="/login"
                className="inline-flex justify-center items-center border-2 border-gray-300 rounded-2xl px-8 py-5 text-xl font-bold bg-white"
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
            appointment — ChairTime lets customers book online or by phone.
            Their appointment goes directly onto your schedule.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-6 mt-14">
          <div className="border border-gray-200 rounded-3xl p-8">
            <div className="text-3xl mb-4">☎️</div>

            <h3 className="text-2xl font-extrabold">
              Never miss a booking
            </h3>

            <p className="mt-3 text-lg text-gray-700 leading-relaxed">
              Customers can book even when you&apos;re busy, with another
              customer, or unable to answer the phone.
            </p>
          </div>

          <div className="border border-gray-200 rounded-3xl p-8">
            <div className="text-3xl mb-4">📅</div>

            <h3 className="text-2xl font-extrabold">
              Keep everything organized
            </h3>

            <p className="mt-3 text-lg text-gray-700 leading-relaxed">
              Your appointments, customer information, notes, schedules,
              confirmations, and reminders stay together.
            </p>
          </div>

          <div className="border border-gray-200 rounded-3xl p-8">
            <div className="text-3xl mb-4">✓</div>

            <h3 className="text-2xl font-extrabold">
              Keep it simple
            </h3>

            <p className="mt-3 text-lg text-gray-700 leading-relaxed">
              ChairTime is designed to be easy for owners, staff,
              and customers without complicated software to learn.
            </p>
          </div>
        </div>
      </section>

      <section className="bg-gray-950 text-white">
        <div className="max-w-6xl mx-auto px-6 py-20">
          <div className="grid md:grid-cols-2 gap-14">
            <div>
              <p className="font-bold text-gray-300 mb-3">
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
              <p className="font-bold text-gray-300 mb-3">
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

      <section className="max-w-5xl mx-auto px-6 py-20 text-center">
        <h2 className="text-4xl sm:text-5xl font-extrabold tracking-tight">
          Set up your shop in minutes.
        </h2>

        <p className="mt-5 text-xl text-gray-700 max-w-2xl mx-auto">
          Add your staff, services, and hours. ChairTime gives your
          business its own booking page and keeps everything organized
          from there.
        </p>

        <Link
          href="/signup"
          className="mt-9 inline-flex justify-center items-center bg-black text-white rounded-2xl px-10 py-5 text-xl font-bold"
        >
          Start My Free Month
        </Link>

        <p className="mt-4 text-gray-600">
          Free for 30 days. No charge today.
        </p>
      </section>

      <footer className="border-t border-gray-200">
        <div className="max-w-6xl mx-auto px-6 py-8 flex flex-col sm:flex-row gap-3 justify-between text-gray-600">
          <p>© 2026 ChairTime</p>

          <Link href="/login" className="font-bold text-gray-900">
            Shop Owner Sign In
          </Link>
        </div>
      </footer>
    </main>
  );
}
