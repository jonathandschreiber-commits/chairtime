"use client";

import { useEffect, useState } from "react";

const API_BASE = "https://chairtime-production-94da.up.railway.app";

export default function AdminPage() {
  const [shops, setShops] = useState([]);
  const [barbers, setBarbers] = useState([]);
  const [services, setServices] = useState([]);
  const [blockedTimes, setBlockedTimes] = useState([]);

  const [barberName, setBarberName] = useState("");
  const [serviceName, setServiceName] = useState("");
  const [serviceDuration, setServiceDuration] = useState("");
  const [servicePrice, setServicePrice] = useState("");

  const [blockBarberId, setBlockBarberId] = useState("");
  const [blockStart, setBlockStart] = useState("");
  const [blockEnd, setBlockEnd] = useState("");
  const [blockReason, setBlockReason] = useState("Lunch");

  const [message, setMessage] = useState("");

  async function loadData() {
    const [shopsRes, barbersRes, servicesRes, blockedRes] = await Promise.all([
      fetch(`${API_BASE}/api/shops`),
      fetch(`${API_BASE}/api/barbers`),
      fetch(`${API_BASE}/api/services`),
      fetch(`${API_BASE}/api/blocked-times`),
    ]);

    const barbersData = await barbersRes.json();

    setShops(await shopsRes.json());
    setBarbers(barbersData);
    setServices(await servicesRes.json());
    setBlockedTimes(await blockedRes.json());

    if (barbersData.length > 0 && !blockBarberId) {
      setBlockBarberId(barbersData[0].id);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  async function addBarber() {
    if (!barberName) {
      setMessage("Please enter a barber name.");
      return;
    }

    await fetch(`${API_BASE}/api/barbers`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        name: barberName,
        shop_name: "ChairTime Barbershop",
        phone: "",
        timezone: "America/New_York",
      }),
    });

    setBarberName("");
    setMessage("Barber added.");
    loadData();
  }

  async function addService() {
    if (!serviceName || !serviceDuration || !servicePrice) {
      setMessage("Please complete all service fields.");
      return;
    }

    const mainBarberId = "c36fbd7b-c3a7-46ce-aa01-6d3952de4b5d";

    await fetch(`${API_BASE}/api/services`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        barber_id: mainBarberId,
        name: serviceName,
        duration_minutes: Number(serviceDuration),
        price: Number(servicePrice),
      }),
    });

    setServiceName("");
    setServiceDuration("");
    setServicePrice("");
    setMessage("Service added.");
    loadData();
  }

  async function blockTime() {
    if (!blockBarberId || !blockStart || !blockEnd) {
      setMessage("Please choose barber, start time, and end time.");
      return;
    }

    await fetch(`${API_BASE}/api/blocked-times`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        barber_id: blockBarberId,
        start_datetime: blockStart,
        end_datetime: blockEnd,
        reason: blockReason,
      }),
    });

    setBlockStart("");
    setBlockEnd("");
    setBlockReason("Lunch");
    setMessage("Time blocked.");
    loadData();
  }

  return (
    <main className="min-h-screen bg-gray-100 p-4 sm:p-10">
      <div className="max-w-5xl mx-auto space-y-6">
        <div className="bg-white rounded-2xl shadow p-6 sm:p-8">
          <h1 className="text-4xl font-bold mb-2">ChairTime Admin</h1>

          <p className="text-gray-600">
            Manage shop settings, staff, services, pricing, and blocked time.
          </p>

          {message && <p className="mt-4 font-medium">{message}</p>}
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
          <h2 className="text-2xl font-bold mb-4">Add Barber / Staff</h2>

          <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
            <input
              className="border rounded-xl p-3"
              placeholder="Barber name"
              value={barberName}
              onChange={(e) => setBarberName(e.target.value)}
            />

            <button
              onClick={addBarber}
              className="bg-black text-white rounded-xl px-6 py-3 font-semibold"
            >
              Add Barber
            </button>
          </div>
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
          <h2 className="text-2xl font-bold mb-4">Add Service</h2>

          <div className="grid gap-3 sm:grid-cols-4">
            <input
              className="border rounded-xl p-3"
              placeholder="Service name"
              value={serviceName}
              onChange={(e) => setServiceName(e.target.value)}
            />

            <input
              className="border rounded-xl p-3"
              placeholder="Duration"
              value={serviceDuration}
              onChange={(e) => setServiceDuration(e.target.value)}
            />

            <input
              className="border rounded-xl p-3"
              placeholder="Price"
              value={servicePrice}
              onChange={(e) => setServicePrice(e.target.value)}
            />

            <button
              onClick={addService}
              className="bg-black text-white rounded-xl px-6 py-3 font-semibold"
            >
              Add Service
            </button>
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

        <section className="bg-white rounded-2xl shadow p-6">
          <h2 className="text-2xl font-bold mb-4">Quick Block Time</h2>

          <div className="grid gap-3">
            <select
              className="border rounded-xl p-3"
              value={blockBarberId}
              onChange={(e) => setBlockBarberId(e.target.value)}
            >
              {barbers.map((barber) => (
                <option key={barber.id} value={barber.id}>
                  {barber.name}
                </option>
              ))}
            </select>

            <select
              className="border rounded-xl p-3"
              value={blockReason}
              onChange={(e) => setBlockReason(e.target.value)}
            >
              <option>Lunch</option>
              <option>Break</option>
              <option>Vacation</option>
              <option>Personal</option>
              <option>Closed</option>
            </select>

            <input
              type="datetime-local"
              className="border rounded-xl p-3"
              value={blockStart}
              onChange={(e) => setBlockStart(e.target.value)}
            />

            <input
              type="datetime-local"
              className="border rounded-xl p-3"
              value={blockEnd}
              onChange={(e) => setBlockEnd(e.target.value)}
            />

            <button
              onClick={blockTime}
              className="bg-black text-white rounded-xl px-6 py-3 font-semibold"
            >
              Block Time
            </button>
          </div>
        </section>

        <section className="bg-white rounded-2xl shadow p-6">
          <h2 className="text-2xl font-bold mb-4">Blocked Times</h2>

          <div className="grid gap-3">
            {blockedTimes.map((block) => (
              <div key={block.id} className="border rounded-xl p-4">
                <p className="font-semibold">{block.reason}</p>

                <p className="text-gray-600">
                  {new Date(block.start_datetime).toLocaleString()} →{" "}
                  {new Date(block.end_datetime).toLocaleString()}
                </p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}