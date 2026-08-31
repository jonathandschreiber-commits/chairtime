export default async function AdminHome({ shop = "" }) {
  const basePath = shop ? "/" + shop + "/admin" : "/admin";

  let businessName = "";

  if (shop) {
    try {
      const apiUrl = process.env.CHAIRTIME_API_URL;

      if (apiUrl) {
        const response = await fetch(
          `${apiUrl}/api/shops?shop_slug=${encodeURIComponent(shop)}`,
          {
            cache: "no-store",
          }
        );

        if (response.ok) {
          const shops = await response.json();

          if (
            Array.isArray(shops) &&
            shops.length > 0 &&
            shops[0]?.name
          ) {
            businessName = shops[0].name;
          }
        }
      }
    } catch (error) {
      console.error("Unable to load business name:", error);
    }
  }

  if (!businessName && shop) {
    businessName = shop
      .split("-")
      .filter(Boolean)
      .map(
        (word) =>
          word.charAt(0).toUpperCase() + word.slice(1)
      )
      .join(" ");
  }

  const title = businessName || "ChairTime";

  const buttons = [
    {
      name: "Daily Agenda",
      description: "View and manage today's appointments.",
      href: basePath + "/today",
      icon: "📋",
      cardClass:
        "bg-gradient-to-br from-violet-50 to-purple-100 border-violet-200",
      iconClass:
        "bg-gradient-to-br from-violet-500 to-purple-600",
      arrowClass:
        "text-violet-600 border-violet-300 hover:bg-violet-100",
    },
    {
      name: "Customers",
      description: "Browse and manage your customer list.",
      href: basePath + "/customers",
      icon: "👥",
      cardClass:
        "bg-gradient-to-br from-emerald-50 to-green-100 border-emerald-200",
      iconClass:
        "bg-gradient-to-br from-emerald-500 to-green-600",
      arrowClass:
        "text-emerald-600 border-emerald-300 hover:bg-emerald-100",
    },
    {
      name: "Calendar",
      description: "See your schedule and upcoming bookings.",
      href: basePath + "/calendar",
      icon: "📅",
      cardClass:
        "bg-gradient-to-br from-sky-50 to-blue-100 border-sky-200",
      iconClass:
        "bg-gradient-to-br from-sky-500 to-blue-600",
      arrowClass:
        "text-blue-600 border-blue-300 hover:bg-blue-100",
    },
    {
      name: "Shop Setup",
      description: "Manage hours, availability, and shop settings.",
      href: basePath + "/setup",
      icon: "🏪",
      cardClass:
        "bg-gradient-to-br from-orange-50 to-amber-100 border-orange-200",
      iconClass:
        "bg-gradient-to-br from-orange-500 to-amber-500",
      arrowClass:
        "text-orange-600 border-orange-300 hover:bg-orange-100",
    },
    {
      name: "Staff & Services",
      description: "Manage staff members and the services you offer.",
      href: basePath + "/staff",
      icon: "✂️",
      cardClass:
        "bg-gradient-to-br from-pink-50 to-rose-100 border-pink-200",
      iconClass:
        "bg-gradient-to-br from-pink-500 to-rose-500",
      arrowClass:
        "text-pink-600 border-pink-300 hover:bg-pink-100",
    },
  ];

  return (
    <main className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-sky-50 px-6 py-10">
      <div className="max-w-4xl mx-auto">
        <div className="bg-white/90 rounded-3xl shadow-lg p-7 border border-indigo-100 mb-6">
          <div className="flex items-center gap-5">
            <div className="w-16 h-16 shrink-0 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-3xl shadow-md">
              🪑
            </div>

            <div>
              <p className="text-sm font-extrabold tracking-wider text-indigo-600 uppercase mb-1">
                Admin Dashboard
              </p>

              <h1 className="text-4xl sm:text-5xl font-extrabold text-slate-900 leading-tight">
                {title}
              </h1>

              <p className="text-gray-600 mt-2 text-base">
                Everything you need to manage your business in one place.
              </p>
            </div>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          {buttons.map((button) => (
            <a
              key={button.href}
              href={button.href}
              className={`group rounded-2xl border p-5 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 ${button.cardClass}`}
            >
              <div className="flex items-center gap-4">
                <div
                  className={`w-14 h-14 shrink-0 rounded-2xl flex items-center justify-center text-2xl text-white shadow-sm ${button.iconClass}`}
                >
                  {button.icon}
                </div>

                <div className="flex-1 min-w-0">
                  <h2 className="text-xl font-extrabold text-slate-900">
                    {button.name}
                  </h2>

                  <p className="text-sm text-slate-600 mt-1 leading-relaxed">
                    {button.description}
                  </p>
                </div>

                <div
                  className={`w-10 h-10 shrink-0 rounded-full border-2 flex items-center justify-center text-xl font-bold transition-colors ${button.arrowClass}`}
                >
                  →
                </div>
              </div>
            </a>
          ))}
        </div>

        <p className="text-center text-sm text-slate-500 mt-8">
          Simple scheduling for busy businesses.
        </p>
      </div>
    </main>
  );
}
