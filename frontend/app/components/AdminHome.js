export default function AdminHome({ shop = "" }) {
  const basePath = shop ? "/" + shop + "/admin" : "/admin";
  const title = shop ? shop + " Admin" : "ChairTime Admin";

  const buttons = [
    {
      name: "Daily Agenda",
      href: basePath + "/today",
    },
    {
      name: "Customers",
      href: basePath + "/customers",
    },
    {
      name: "Calendar",
      href: basePath + "/calendar",
    },
    {
      name: "Shop Setup",
      href: basePath + "/setup",
    },
  ];

  return (
    <main className="min-h-screen bg-gray-100 p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="bg-white rounded-3xl shadow-lg p-6 border">
          <h1 className="text-5xl font-extrabold mb-2">{title}</h1>

          <p className="text-gray-700">
            ChairTime shop admin dashboard
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          {buttons.map((button) => (
            <a
              key={button.href}
              href={button.href}
              className="bg-black text-white rounded-2xl p-6 text-center font-bold text-xl"
            >
              {button.name}
            </a>
          ))}
        </div>
      </div>
    </main>
  );
}