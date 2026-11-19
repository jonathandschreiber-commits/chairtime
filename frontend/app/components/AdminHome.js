import { ShopMessage } from "./ShopLanguage";
import { cookies } from "next/headers";
import AdminUserBar from "./AdminUserBar";
import SavePageShortcut from "./SavePageShortcut";
 
const COOKIE_NAME = "chairtime_token";
 
 
export default async function AdminHome({
  shop = "",
  showShopInfo = false,
}) {
  const basePath = shop
    ? "/" + shop + "/admin"
    : "/admin";
 
  let businessName = "";
  let businessPhone = "";
  let aiPhoneNumber = "";
  let bookingQrCode = "";
  let aiVoiceEnabled = false;
 
  let currentUser = null;
  let isOwner = false;
  let isStaff = false;
 
  const apiUrl =
    process.env.CHAIRTIME_API_URL;
 
 
  /*
   * Load the authenticated DayTello user.
   *
   * The JWT remains in the HTTP-only cookie and
   * is never exposed to client-side JavaScript.
   */
  try {
    const cookieStore =
      await cookies();
 
    const token =
      cookieStore.get(
        COOKIE_NAME
      )?.value;
 
    if (apiUrl && token) {
      const response = await fetch(
        `${apiUrl}/api/auth/me`,
        {
          method: "GET",
          headers: {
            Accept: "application/json",
            Authorization:
              `Bearer ${token}`,
          },
          cache: "no-store",
        }
      );
 
      if (response.ok) {
        currentUser =
          await response.json();
 
        isOwner =
          currentUser?.role ===
          "owner";
 
        isStaff =
          currentUser?.role ===
          "staff";
      }
    }
  } catch (error) {
    console.error(
      "Unable to load authenticated user:",
      error
    );
  }
 
 
  /*
   * Load the business information.
   */
  if (shop) {
    try {
      if (apiUrl) {
        const cookieStore =
          await cookies();
 
        const token =
          cookieStore.get(
            COOKIE_NAME
          )?.value;
 
        if (token) {
          const response = await fetch(
            `${apiUrl}/api/shops/${encodeURIComponent(
              shop
            )}/account`,
            {
              method: "GET",
              headers: {
                Accept: "application/json",
                Authorization:
                  `Bearer ${token}`,
              },
              cache: "no-store",
            }
          );
 
          if (response.ok) {
            const currentShop =
              await response.json();
            businessPhone = currentShop?.phone || "";
            aiPhoneNumber = currentShop?.ai_phone_number || "";
            bookingQrCode = currentShop?.booking_qr_code || "";
 
            if (
              currentShop?.name
            ) {
              businessName =
                currentShop.name;
            }
 
            aiVoiceEnabled =
              Boolean(
                currentShop
                  ?.ai_voice_enabled
              );
          }
        }
      }
    } catch (error) {
      console.error(
        "Unable to load business information:",
        error
      );
    }
  }
 
 
  if (!businessName && shop) {
    businessName = shop
      .split("-")
      .filter(Boolean)
      .map(
        (word) =>
          word
            .charAt(0)
            .toUpperCase() +
          word.slice(1)
      )
      .join(" ");
  }
 
 
  const title =
    businessName || "DayTello";
 
  const currentUserName =
    String(
      currentUser?.name || ""
    ).trim();
 
  const currentUserRole =
    isOwner
      ? "Owner"
      : isStaff
        ? "Staff"
        : "";
 
 
  /*
   * These pages are available to both owners
   * and employees.
   *
   * The individual pages and backend endpoints
   * will also enforce employee permissions.
   */
  const operationalButtons = [
    {
      name: "Daily Agenda",
      description:
        isStaff
          ? "View and manage your appointments."
          : "View and manage today's appointments.",
      href:
        basePath + "/today",
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
      description:
        isStaff
          ? "View customers and customer information."
          : "Browse and manage your customer list.",
      href:
        basePath + "/customers",
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
      description:
        isStaff
          ? "View the shop schedule and your appointments."
          : "See your schedule and upcoming bookings.",
      href:
        basePath + "/calendar",
      icon: "📅",
      cardClass:
        "bg-gradient-to-br from-sky-50 to-blue-100 border-sky-200",
      iconClass:
        "bg-gradient-to-br from-sky-500 to-blue-600",
      arrowClass:
        "text-blue-600 border-blue-300 hover:bg-blue-100",
    },
  ];
 
 
  /*
   * Owner-only business administration.
   */
  const ownerButtons = [
    {
      name: "Time Sheet Report",
      description: "Review weekly hours, hourly pay, commission, and total compensation.",
      href: basePath + "/timesheets",
      icon: "🕒",
      cardClass: "bg-gradient-to-br from-blue-50 to-indigo-100 border-blue-200",
      iconClass: "bg-gradient-to-br from-blue-500 to-indigo-600",
      arrowClass: "text-indigo-600 border-indigo-300 hover:bg-indigo-100",
    },
    {
      name: "Shop Setup",
      description:
        "Manage hours, availability, and shop settings.",
      href:
        basePath + "/setup",
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
      description:
        "Manage staff members and the services you offer.",
      href:
        basePath + "/staff",
      icon: "✂️",
      cardClass:
        "bg-gradient-to-br from-pink-50 to-rose-100 border-pink-200",
      iconClass:
        "bg-gradient-to-br from-pink-500 to-rose-500",
      arrowClass:
        "text-pink-600 border-pink-300 hover:bg-pink-100",
    },
 
    ...(aiVoiceEnabled
      ? [
          {
            name:
              "AI Receptionist",
            description:
              "Test and manage your AI phone receptionist.",
            href:
              basePath +
              "/ai-receptionist",
            icon: "🤖",
            cardClass:
              "bg-gradient-to-br from-fuchsia-50 to-violet-100 border-fuchsia-200",
            iconClass:
              "bg-gradient-to-br from-fuchsia-500 to-violet-600",
            arrowClass:
              "text-fuchsia-600 border-fuchsia-300 hover:bg-fuchsia-100",
          },
        ]
      : []),
 
    ...(aiVoiceEnabled
      ? [{
          name: "AI Usage & Billing",
          description: "See your AI minutes and usage charges.",
          href: basePath + "/ai-usage",
          icon: "📊",
          cardClass: "bg-gradient-to-br from-indigo-50 to-violet-100 border-indigo-200",
          iconClass: "bg-gradient-to-br from-indigo-500 to-violet-600",
          arrowClass: "text-indigo-600 border-indigo-300 hover:bg-indigo-100",
        }]
      : []),

    {
      name: "Account Options",
      description:
        "Manage your subscription, payments, and billing settings.",
      href:
        basePath + "/account",
      icon: "⚙️",
      cardClass:
        "bg-gradient-to-br from-slate-50 to-gray-100 border-slate-200",
      iconClass:
        "bg-gradient-to-br from-slate-600 to-gray-700",
      arrowClass:
        "text-slate-700 border-slate-300 hover:bg-slate-100",
    },
  ];
 
 
  /*
   * Owners receive all controls.
   * Staff receive only operational controls.
   *
   * If authentication cannot be verified,
   * do not expose owner-only navigation.
   */
  const buttons = isOwner
    ? [
        {
          name: "Your Shop Info",
          description: "Your shop links, QR code, phone numbers, and setup instructions.",
          href: basePath + "/shop-info",
          icon: "🏪",
          cardClass: "bg-gradient-to-br from-indigo-50 to-violet-100 border-indigo-200",
          iconClass: "bg-gradient-to-br from-indigo-500 to-violet-600",
          arrowClass: "text-indigo-600 border-indigo-300 hover:bg-indigo-100",
        },
        ...operationalButtons,
        ...ownerButtons,
      ]
    : operationalButtons;
 
 
  return (
    <main className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-sky-50 px-6 py-10">
      <div className="max-w-5xl mx-auto">
        <div className="mb-4">
          <AdminUserBar />
        </div>
 
        <div className="bg-white/90 rounded-3xl shadow-lg p-7 border border-indigo-100 mb-6">
          <div className="flex items-start gap-5">
            <div className="w-16 h-16 shrink-0 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-3xl shadow-md">
              🪑
            </div>
 
            <div className="flex-1 min-w-0">
              <p className="text-sm font-extrabold tracking-wider text-indigo-600 uppercase mb-1">
                <ShopMessage>{isStaff ? "Staff Dashboard" : "Admin Dashboard"}</ShopMessage>
              </p>
 
              <h1 className="text-4xl sm:text-5xl font-extrabold text-slate-900 leading-tight">
                {showShopInfo ? <ShopMessage>Your Shop Info</ShopMessage> : title}
              </h1>
 
              {currentUserName &&
                currentUserRole && (
                  <p className="mt-2 text-lg font-bold text-indigo-700">
                    {currentUserName}
                    {" · "}
                    <ShopMessage>{currentUserRole}</ShopMessage>
                  </p>
                )}
 
              <p className="text-gray-600 mt-2 text-base">
                <ShopMessage>{isStaff
                  ? "Appointments and customer information for your workday."
                  : "Everything you need to manage your business in one place."}</ShopMessage>
              </p>
            </div>
          </div>
        </div>
 
 
        {showShopInfo && isOwner && shop && (
          <section aria-label="Your DayTello pages" className="mb-6 grid gap-4 sm:grid-cols-2">
            <div className="rounded-2xl border border-indigo-100 bg-white p-5">
              <h2 className="text-lg font-bold text-slate-900"><ShopMessage>Owner dashboard</ShopMessage></h2>
              <p className="mt-1 text-sm text-slate-600">
                <ShopMessage>Use your owner dashboard to set up your services and staff, and manage bookings.</ShopMessage>
              </p>
              <p className="mt-3 break-all text-sm text-slate-700">
                {`daytello.com/${encodeURIComponent(shop)}/admin`}
              </p>
              <a className="mt-2 inline-block text-sm font-semibold text-indigo-700 underline" href={basePath}><ShopMessage>Open your owner dashboard</ShopMessage></a>
            </div>
            <div className="rounded-2xl border border-indigo-100 bg-white p-5">
              <h2 className="text-lg font-bold text-slate-900"><ShopMessage>Customer booking page</ShopMessage></h2>
              <p className="mt-1 text-sm text-slate-600">
                <ShopMessage>Open this page to see what customers see. Share this link so they can book.</ShopMessage>
              </p>
              <a
                href={`/${encodeURIComponent(shop)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-3 inline-block break-all text-sm font-semibold text-indigo-700 underline"
              >
                {`daytello.com/${encodeURIComponent(shop)}`}
              </a>
              {bookingQrCode.startsWith("data:image/svg+xml;base64,") && (
                <figure className="mt-3">
                  <img
                    src={bookingQrCode}
                    alt={`<ShopMessage>Scan to book</ShopMessage> with ${title}`}
                    width={108}
                    height={108}
                    className="rounded-lg border border-slate-200 bg-white"
                  />
                  <figcaption className="mt-1 text-sm text-slate-600">Scan to book</figcaption>
                </figure>
              )}
            </div>
          </section>
        )}

        {showShopInfo && isOwner && shop && (businessPhone || aiVoiceEnabled) && (
          <section className="mb-6 rounded-2xl border border-indigo-100 bg-white p-5" aria-labelledby="shop-phone-heading">
            <h2 id="shop-phone-heading" className="text-lg font-bold text-slate-900"><ShopMessage>Shop phone &amp; call forwarding</ShopMessage></h2>
            <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
              <div>
                <dt className="font-semibold text-slate-700"><ShopMessage>Existing shop phone</ShopMessage></dt>
                <dd className="mt-1">
                  {businessPhone ? <a className="text-indigo-700 underline" href={`tel:${businessPhone}`}>{businessPhone}</a> : <ShopMessage>No shop phone on file</ShopMessage>}
                </dd>
              </div>
              {aiVoiceEnabled && (
                <div>
                  <dt className="font-semibold text-slate-700"><ShopMessage>DayTello AI Receptionist number</ShopMessage></dt>
                  <dd className="mt-1">
                    {aiPhoneNumber ? <a className="text-indigo-700 underline" href={`tel:${aiPhoneNumber}`}>{aiPhoneNumber}</a> : <ShopMessage>Number setup is pending</ShopMessage>}
                  </dd>
                </div>
              )}
            </dl>
            {aiVoiceEnabled && aiPhoneNumber && (
              <div className="mt-4 text-sm text-slate-700">
                <h3 className="font-semibold"><ShopMessage>Forward calls from your existing shop phone</ShopMessage></h3>
                <ol className="mt-2 list-decimal space-y-1 pl-5">
                  <li><ShopMessage>Call your DayTello AI number first and confirm the receptionist answers.</ShopMessage></li>
                  <li><ShopMessage>In your current phone provider’s call-forwarding settings, set the destination to</ShopMessage>{" "}<strong>{aiPhoneNumber}</strong>.{" "}<ShopMessage>Choose all calls or unanswered calls, if supported.</ShopMessage></li>
                  <li><ShopMessage>From another phone, call your existing shop number to confirm it reaches the receptionist.</ShopMessage></li>
                </ol>
                <p className="mt-2"><ShopMessage>For live transfers, use a different number from the one you forward to DayTello. This avoids a call loop.</ShopMessage></p>
              </div>
            )}
            {aiVoiceEnabled && (
              <a className="mt-3 inline-block text-sm font-semibold text-indigo-700 underline" href={`${basePath}/ai-receptionist`}>
                <ShopMessage>{aiPhoneNumber ? "Test or manage your AI Receptionist" : "Continue AI phone setup"}</ShopMessage>
              </a>
            )}
          </section>
        )}

        {showShopInfo && (
          <a href={basePath} className="mb-5 inline-block font-semibold text-indigo-700 underline"><ShopMessage>Back to dashboard</ShopMessage></a>
        )}
        {!showShopInfo && isOwner && <div className="mb-4"><SavePageShortcut pageName="your owner dashboard" /></div>}
        {!showShopInfo && <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {buttons.map(
            (button) => (
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
                      <ShopMessage>{button.name}</ShopMessage>
                    </h2>
 
                    <p className="text-sm text-slate-600 mt-1 leading-relaxed">
                      <ShopMessage>{button.description}</ShopMessage>
                    </p>
                  </div>
 
                  <div
                    className={`w-10 h-10 shrink-0 rounded-full border-2 flex items-center justify-center text-xl font-bold transition-colors ${button.arrowClass}`}
                  >
                    →
                  </div>
                </div>
              </a>
            )
          )}
        </div>}
 
 
        <p className="text-center text-sm text-slate-500 mt-8">
          <ShopMessage>Simple scheduling for busy businesses.</ShopMessage>
        </p>
      </div>
    </main>
  );
}

