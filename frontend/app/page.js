"use client";

import { useEffect, useState } from "react";

const API_BASE = "https://chairtime-production-94da.up.railway.app";

export default function Home() {
  const today = new Date().toISOString().slice(0, 10);

  const [barbers, setBarbers] = useState([]);
  const [services, setServices] = useState([]);
  const [slots, setSlots] = useState([]);

  const [selectedBarberId, setSelectedBarberId] = useState("");
  const [selectedServiceId, setSelectedServiceId] = useState("");
  const [selectedDate, setSelectedDate] = useState(today);
  const [selectedSlot, setSelectedSlot] = useState("");

  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [message, setMessage] = useState("");

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

  async function loadSlots(barberId, serviceId, dateValue) {
    if (!barberId || !serviceId || !dateValue) return;

    setSelectedSlot("");
    setMessage("");

    const response = await fetch(
      `${API_BASE}/api/availability?barber_id=${barberId}&service_id=${serviceId}&target_date=${dateValue}`
    );

    const data = await response.json();

    setSlots(data.slots || []);
  }

  useEffect(() => {
    loadInitialData();
  }, []);

  useEffect(() => {
    if (selectedBarberId && selectedServiceId && selectedDate) {
      loadSlots(selectedBarberId, selectedServiceId, selectedDate);
    }
  }, [selectedBarberId, selectedServiceId, selectedDate]);

  async function bookAppointment() {
    if (!selectedBarberId) {
      setMessage("Please choose a barber.");
      return;
    }

    if (!selectedServiceId) {
      setMessage("Please choose a service.");
      return;
    }

    if (!selectedDate) {
      setMessage("Please choose a date.");
      return;
    }

    if (!selectedSlot) {
      setMessage("Please choose a time.");
      return;
    }

    if (!customerName) {
      setMessage("Please enter your name.");
      return;
    }

    if (!customerPhone) {
      setMessage("Please enter your phone number.");
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
        customer_name: customerName,
        customer_phone: customerPhone,
        start_datetime: selectedSlot,
      }),
    });

    if (response.ok) {
      setMessage("Appointment booked successfully.");
      setCustomerName("");
      setCustomerPhone("");
      setSelectedSlot("");
      loadSlots(selectedBarberId, selectedServiceId, selectedDate);
    } else if (response.status === 409) {
      setMessage("That time was just booked. Please choose another time.");
      loadSlots(selectedBarberId, selectedServiceId, selectedDate);
    } else {
      setMessage("Booking failed. Please try again.");
    }
  }

  function formatTime(slot) {
    return new Date(slot).toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit",
    });
  }

  return (
    <main className="min-h-screen bg-gray-100 p-4 sm:p-10">
      <div className="max-w-3xl mx-auto bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-gray-200">
        <h1 className="text-5xl font-extrabold tracking-tight mb-3">
          ChairTime
        </h1>

        <p className="text-gray-900 mb-8">Book your appointment</p>

        <section className="mb-8">
          <h2 className="text-2xl font-bold mb-4">Choose a barber</h2>

          <div className="grid gap-3">
            {barbers.map((barber) => (
              <button
                key={barber.id}
                type="button"
                onClick={() => setSelectedBarberId(barber.id)}
                className={`border rounded-xl p-4 text-left font-semibold ${
                  selectedBarberId === barber.id
                    ? "bg-black text-white"
                    : "bg-white text-gray-900"
                }`}
              >
                {barber.name}
              </button>
            ))}
          </div>
        </section>

        <section className="mb-8">
          <h2 className="text-2xl font-bold mb-4">Choose a service</h2>

          <div className="grid gap-3">
            {services.map((service) => (
              <button
                key={service.id}
                type="button"
                onClick={() => setSelectedServiceId(service.id)}
                className={`border rounded-xl p-4 text-left ${
                  selectedServiceId === service.id
                    ? "bg-black text-white"
                    : "bg-white text-gray-900"
                }`}
              >
                <div className="font-semibold">{service.name}</div>
                <div className="text-sm">
                  ${service.price} · {service.duration_minutes} minutes
                </div>
              </button>
            ))}
          </div>
        </section>

        <section className="mb-8">
          <h2 className="text-2xl font-bold mb-4">Choose a date</h2>

          <input
            type="date"
            className="w-full border rounded-xl p-3"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
          />
        </section>

        <section className="mb-8">
          <h2 className="text-2xl font-bold mb-4">Choose a time</h2>

          <div className="grid grid-cols-2 gap-3">
            {slots.length === 0 && (
              <p className="text-gray-900 col-span-2">
                No available times for this barber, service, and date.
              </p>
            )}

            {slots.map((slot) => (
              <button
                key={slot}
                type="button"
                onClick={() => setSelectedSlot(slot)}
                className={`border rounded-xl p-4 text-left font-semibold ${
                  selectedSlot === slot
                    ? "bg-black text-white"
                    : "bg-white text-gray-900"
                }`}
              >
                {formatTime(slot)}
              </button>
            ))}
          </div>
        </section>

        <section className="space-y-4">
          <input
            className="w-full border rounded-xl p-3"
            placeholder="Your name"
            value={customerName}
            onChange={(e) => setCustomerName(e.target.value)}
          />

          <input
            className="w-full border rounded-xl p-3"
            placeholder="Phone number"
            value={customerPhone}
            onChange={(e) => setCustomerPhone(e.target.value)}
          />

          <button
            type="button"
            onClick={bookAppointment}
            className="w-full bg-black text-white rounded-xl p-4 font-semibold"
          >
            Book Appointment
          </button>
        </section>

        {message && (
          <p className="mt-6 font-semibold text-gray-900">{message}</p>
        )}
      </div>
    </main>
  );
}