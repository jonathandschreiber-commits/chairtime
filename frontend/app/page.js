"use client";

import { useEffect, useState } from "react";

const API_BASE = "https://chairtime-production-94da.up.railway.app";

export default function Home() {
  const [barbers, setBarbers] = useState([]);
  const [services, setServices] = useState([]);
  const [slots, setSlots] = useState([]);

  const [selectedBarber, setSelectedBarber] = useState("");
  const [selectedService, setSelectedService] = useState("");
  const [selectedDate, setSelectedDate] = useState("2026-05-15");
  const [selectedSlot, setSelectedSlot] = useState("");

  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [message, setMessage] = useState("");

  async function loadBarbers() {
    const response = await fetch(`${API_BASE}/api/barbers`);
    const data = await response.json();

    setBarbers(data);

    if (data.length > 0) {
      setSelectedBarber(data[0].id);
    }
  }

  async function loadServices() {
    const response = await fetch(`${API_BASE}/api/services`);
    const data = await response.json();

    setServices(data);

    if (data.length > 0) {
      setSelectedService(data[0].id);
    }
  }

  async function loadSlots(
    dateToLoad = selectedDate,
    barberId = selectedBarber,
    serviceId = selectedService
  ) {
    if (!barberId || !serviceId) return;

    setMessage("");
    setSelectedSlot("");

    const response = await fetch(
      `${API_BASE}/api/availability?barber_id=${barberId}&service_id=${serviceId}&target_date=${dateToLoad}`
    );

    const data = await response.json();
    setSlots(data.slots || []);
  }

  useEffect(() => {
    loadBarbers();
    loadServices();
  }, []);

  useEffect(() => {
    if (selectedBarber && selectedService) {
      loadSlots(selectedDate, selectedBarber, selectedService);
    }
  }, [selectedBarber, selectedService]);

  function handleDateChange(e) {
    const newDate = e.target.value;
    setSelectedDate(newDate);
    loadSlots(newDate, selectedBarber, selectedService);
  }

  async function bookAppointment() {
    setMessage("");

    if (
      !selectedBarber ||
      !selectedService ||
      !selectedSlot ||
      !customerName ||
      !customerPhone
    ) {
      setMessage("Please complete all fields.");
      return;
    }

    const response = await fetch(`${API_BASE}/api/appointments`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        barber_id: selectedBarber,
        service_id: selectedService,
        customer_name: customerName,
        customer_phone: customerPhone,
        start_datetime: selectedSlot,
      }),
    });

    if (response.ok) {
      setMessage("Appointment booked successfully!");
      setSelectedSlot("");
      setCustomerName("");
      setCustomerPhone("");
      loadSlots(selectedDate, selectedBarber, selectedService);
    } else if (response.status === 409) {
      setMessage("That time was just booked.");
      loadSlots(selectedDate, selectedBarber, selectedService);
    } else {
      setMessage("Booking failed.");
    }
  }

  return (
    <main className="min-h-screen bg-gray-100 p-4 sm:p-10">
      <div className="max-w-2xl mx-auto bg-white rounded-2xl shadow p-6 sm:p-8">
        <h1 className="text-4xl font-bold mb-2">ChairTime</h1>

        <p className="text-gray-600 mb-8">Book your appointment</p>

        <label className="block font-semibold mb-2">Choose a barber</label>

        <div className="grid grid-cols-1 gap-3 mb-6">
          {barbers.map((barber) => (
            <button
              key={barber.id}
              onClick={() => setSelectedBarber(barber.id)}
              className={`p-4 border rounded-xl text-left ${
                selectedBarber === barber.id
                  ? "bg-black text-white"
                  : "bg-white"
              }`}
            >
              <div className="font-semibold">{barber.name}</div>
              <div className="text-sm">{barber.shop_name}</div>
            </button>
          ))}
        </div>

        <label className="block font-semibold mb-2">Choose a service</label>

        <div className="grid grid-cols-1 gap-3 mb-6">
          {services.map((service) => (
            <button
              key={service.id}
              onClick={() => setSelectedService(service.id)}
              className={`p-4 border rounded-xl text-left ${
                selectedService === service.id
                  ? "bg-black text-white"
                  : "bg-white"
              }`}
            >
              <div className="font-semibold">{service.name}</div>
              <div className="text-sm">
                ${service.price} · {service.duration_minutes} minutes
              </div>
            </button>
          ))}
        </div>

        <label className="block font-semibold mb-2">Choose a date</label>

        <input
          type="date"
          value={selectedDate}
          onChange={handleDateChange}
          className="w-full border rounded-xl p-3 mb-8"
        />

        <div className="grid grid-cols-2 gap-3 mb-8">
          {slots.length === 0 && (
            <p className="text-gray-500 col-span-2">No available times.</p>
          )}

          {slots.map((slot) => (
            <button
              key={slot}
              onClick={() => setSelectedSlot(slot)}
              className={`p-4 border rounded-xl text-left ${
                selectedSlot === slot ? "bg-black text-white" : "bg-white"
              }`}
            >
              {new Date(slot).toLocaleTimeString([], {
                hour: "numeric",
                minute: "2-digit",
              })}
            </button>
          ))}
        </div>

        <div className="space-y-4">
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
            onClick={bookAppointment}
            className="w-full bg-black text-white rounded-xl p-4 font-semibold"
          >
            Book Appointment
          </button>
        </div>

        {message && <p className="mt-6 font-medium">{message}</p>}
      </div>
    </main>
  );
}