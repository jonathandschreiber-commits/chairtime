"use client";

import { useEffect, useState } from "react";
import Script from "next/script";

const API_BASE = "https://chairtime-production-94da.up.railway.app";

export default function HomePage() {
  const today = new Date().toISOString().slice(0, 10);

  const [barbers, setBarbers] = useState([]);
  const [services, setServices] = useState([]);
  const [availableSlots, setAvailableSlots] = useState([]);

  const [selectedBarberId, setSelectedBarberId] = useState("");
  const [selectedServiceId, setSelectedServiceId] = useState("");
  const [selectedDate, setSelectedDate] = useState(today);
  const [selectedTime, setSelectedTime] = useState("");

  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [notes, setNotes] = useState("");

  const [message, setMessage] = useState("");

  useEffect(() => {
    loadInitialData();
  }, []);

  useEffect(() => {
    if (selectedBarberId && selectedServiceId && selectedDate) {
      loadAvailability();
    }
  }, [selectedBarberId, selectedServiceId, selectedDate]);

  async function loadInitialData() {
    const [barbersRes, servicesRes] = await Promise.all([
      fetch(`${API_BASE}/api/barbers`),
      fetch(`${API_BASE}/api/services`),
    ]);

    const barbersData = await barbersRes.json();
    const servicesData = await servicesRes.json();

    setBarbers(barbersData);
    setServices(servicesData);

    if (barbersData.length > 0) {
      setSelectedBarberId(barbersData[0].id);
    }

    if (servicesData.length > 0) {
      setSelectedServiceId(servicesData[0].id);
    }
  }

  async function loadAvailability() {
    setSelectedTime("");

    const response = await fetch(
      `${API_BASE}/api/availability?barber_id=${selectedBarberId}&service_id=${selectedServiceId}&target_date=${selectedDate}`
    );

    const data = await response.json();

    setAvailableSlots(data.slots || []);
  }

  function formatTime(value) {
    return new Date(value).toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit",
    });
  }

  async function createAppointment() {
    if (
      !selectedBarberId ||
      !selectedServiceId ||
      !selectedTime ||
      !customerName ||
      !customerPhone
    ) {
      setMessage("Please complete all required fields.");
      return;
    }

    const response = await fetch(`${API_BASE}/api/appointments`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        barber_id: selectedBarberId,
        service_id: selectedServiceId,
        start_datetime: selectedTime,
        customer_name: customerName,
        customer_phone: customerPhone,
        notes: notes || null,
      }),
    });

    if (response.ok) {
      setMessage("Appointment booked successfully.");

      setSelectedTime("");
      setCustomerName("");
      setCustomerPhone("");
      setNotes("");

      loadAvailability();
    } else {
      setMessage("Could not create appointment.");
    }
  }

  return (
    <>
      <Script
        src="https://widgets.leadconnectorhq.com/loader.js"
        data-resources-url="https://widgets.leadconnectorhq.com/chat-widget/loader.js"
        data-widget-id="6a1da28d5bbf369793465aa2"
        data-source="WEB_USER"
        strategy="afterInteractive"
      />

      <main className="min-h-screen bg-gray-100 p-4 sm:p-10">
        <div className="max-w-3xl mx-auto bg-white rounded-3xl shadow-lg p-6 sm:p-10 border border-gray-200">
          <h1 className="text-5xl font-extrabold tracking-tight mb-3">
            ChairTime
          </h1>

          <p className="text-gray-900 mb-8">Book your next appointment.</p>

          {message && (
            <div className="mb-6 p-4 rounded-xl bg-green-100 text-green-800 font-semibold">
              {message}
            </div>
          )}

          <div className="grid gap-6">
            <div>
              <label className="block font-semibold mb-2">Barber</label>

              <select
                className="w-full border rounded-xl p-3"
                value={selectedBarberId}
                onChange={(e) => setSelectedBarberId(e.target.value)}
              >
                {barbers.map((barber) => (
                  <option key={barber.id} value={barber.id}>
                    {barber.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block font-semibold mb-2">Service</label>

              <select
                className="w-full border rounded-xl p-3"
                value={selectedServiceId}
                onChange={(e) => setSelectedServiceId(e.target.value)}
              >
                {services.map((service) => (
                  <option key={service.id} value={service.id}>
                    {service.name} — ${service.price}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block font-semibold mb-2">Date</label>

              <input
                type="date"
                className="w-full border rounded-xl p-3"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
              />
            </div>

            <div>
              <label className="block font-semibold mb-2">Available Times</label>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {availableSlots.map((slot) => (
                  <button
                    key={slot}
                    onClick={() => setSelectedTime(slot)}
                    className={`border rounded-xl p-3 font-semibold ${
                      selectedTime === slot ? "bg-black text-white" : "bg-white"
                    }`}
                  >
                    {formatTime(slot)}
                  </button>
                ))}
              </div>

              {availableSlots.length === 0 && (
                <p className="text-gray-900 mt-3">
                  No available times for this barber, service, and date.
                </p>
              )}
            </div>

            <div>
              <label className="block font-semibold mb-2">Your Name</label>

              <input
                className="w-full border rounded-xl p-3"
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
              />
            </div>

            <div>
              <label className="block font-semibold mb-2">Phone Number</label>

              <input
                className="w-full border rounded-xl p-3"
                value={customerPhone}
                onChange={(e) => setCustomerPhone(e.target.value)}
              />
            </div>

            <div>
              <label className="block font-semibold mb-2">
                Notes <span className="font-normal text-gray-600">(optional)</span>
              </label>

              <textarea
                className="w-full border rounded-xl p-3 min-h-24"
                placeholder="Example: skin fade, gel removal, prefers quiet chair"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </div>

            <button
              onClick={createAppointment}
              className="bg-black text-white rounded-xl px-6 py-4 font-bold text-lg"
            >
              Book Appointment
            </button>
          </div>
        </div>
      </main>
    </>
  );
}