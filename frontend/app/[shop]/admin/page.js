export default async function ShopAdminPage({ params }) {
  const { shop } = await params;

  return (
    <main className="min-h-screen bg-gray-100 p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="bg-white rounded-3xl shadow-lg p-6 border">
          <h1 className="text-5xl font-extrabold mb-2">
            {shop} Admin
          </h1>

          <p className="text-gray-700">
            ChairTime shop admin dashboard
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <a
            href={`/${shop}/admin/today`}
            className="bg-black text-white rounded-2xl p-6 text-center font-bold text-xl"
          >
            Daily Agenda
          </a>

          <a
            href={`/${shop}/admin/customers`}
            className="bg-black text-white rounded-2xl p-6 text-center font-bold text-xl"
          >
            Customers
          </a>

          <a
            href={`/${shop}/admin/calendar`}
            className="bg-black text-white rounded-2xl p-6 text-center font-bold text-xl"
          >
            Calendar
          </a>

          <a
            href={`/${shop}/admin/setup`}
            className="bg-black text-white rounded-2xl p-6 text-center font-bold text-xl"
          >
            Shop Setup
          </a>
        </div>
      </div>
    </main>
  );
}