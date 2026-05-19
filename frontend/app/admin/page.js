"use client";

import { useEffect, useState } from "react";

const API_BASE = "https://chairtime-production-94da.up.railway.app";

export default function AdminPage() {
  const [shops, setShops] = useState([]);
  const [barbers, setBarbers] = useState([]);
  const [services, setServices] = useState([]);

  async function loadData() {
    const [shopsRes, barbersRes, servicesRes] = await Promise.all([
      fetch(`${API_BASE}/api/shops`),
      fetch(`${API_BASE}/api/barbers`),
      fetch(`${API_BASE}/api/services`),
    ]);

    setShops(await shopsRes.json());
    setBarbers(await barbersRes.json());
    setServices(await servicesRes.json());
  }

  useEffect(() => {
    loadData();
  }, []);

  return (
    <main className="min-h-screen bg-gray-100 p-4 sm:p-10">
      <div className="max-w-5xl mx-auto space-y-6">
        <div className="bg-white rounded-2xl shadow p-6 sm:p-8">
          <h1 className="text-4xl font-bold mb-2">ChairTime Admin</h1>
          <p className="text-gray-600">
            Manage shop settings, staff, services, and pricing.
          </p>
        </div>

        <section className="bg-white rounded-2xl shadow p-6">
          <h2 className="text-2xl font-bold mb-4">Shop Settings</h2>

          {shops.map((shop) => (
            <div key={shop.id} className="border rounded-xl p-4">
              <p className="font-semibold">{shop.name}</p>
              <p>Type: {shop.business_type}</p>
              <p>Phone: {shop.phone}</p>
              <p>Accepts Cards: {shop.accepts_cards ? "Yes" : "No"}</p>
              <p>Requires Deposit: {shop.requires_deposit ? "Yes" : "No"}</p>
              <p>Deposit Amount: ${shop.deposit_amount || 0}</p>
              <p>No-Show Fee: ${shop.no_show_fee || 0}</p>
            </div>
          ))}
        </section>

        <section className="bg-white rounded-2xl shadow p-6">
          <h2 className="text-2xl font-bold mb-4">Barbers / Staff</h2>

          <div className="grid gap-3">
            {barbers.map((barber) => (
              <div key={barber.id} className="border rounded-xl p-4">
                <p className="font-semibold">{barber.name}</p>
                <p className="text-gray-600">{barber.shop_name}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="bg-white rounded-2xl shadow p-6">
          <h2 className="text-2xl font-bold mb-4">Services</h2>

          <div className="grid gap-3">
            {services.map((service) => (
              <div
                key={service.id}
                className="border rounded-xl p-4 flex justify-between"
              >
                <div>
                  <p className="font-semibold">{service.name}</p>
                  <p className="text-gray-600">
                    {service.duration_minutes} minutes
                  </p>
                </div>

                <p className="font-bold">${service.price}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}