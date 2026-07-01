"use client";

import Link from "next/link";

export default function AdminPage() {
  const buttons = [
    {
      name: "Today's Agenda",
      href: "/admin/today",
    },
    {
      name: "Customers",
      href: "/admin/customers",
    },
    {
      name: "Calendar",
      href: "/admin/calendar",
    },
    {
      name: "Shop Setup",
      href: "/admin/setup",
    },
    {
      name: "Dashboard",
      href: "/dashboard",
    },
  ];

  return (
    <main className="min-h-screen bg-gray-100 p-6 sm:p-10">
      <div className="max-w-4xl mx-auto">
        <div className="bg-white rounded-3xl shadow-lg p-8 border border-gray-200">
          <h1 className="text-5xl font-extrabold mb-3">
            ChairTime Admin
          </h1>

          <p className="text-lg text-gray-700 mb-8">
            Everything in one place.
          </p>

          <div className="grid gap-4">
            {buttons.map((button) => (
              <Link
                key={button.href}
                href={button.href}
                className="bg-black text-white rounded-2xl px-6 py-5 text-2xl font-bold text-center"
              >
                {button.name}
              </Link>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}