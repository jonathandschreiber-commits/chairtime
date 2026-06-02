"use client";

import { useEffect, useMemo, useState } from "react";

const API_BASE =
  "https://chairtime-production-94da.up.railway.app";

export default function HomePage() {
  const today = new Date().toISOString().slice(0, 10);

  const [barbers, setBarbers] = useState([]);
  const [services, setServices] = useState([]);
  const [appointments, setAppointments] = useState([]);
  const [availableSlots, setAvailableSlots] = useState([]);

  const [customerName, setCustomerName] =
    useState("");

  const [customerPhone, setCustomerPhone] =
    useState("");

  const [notes, setNotes] = useState("");

  const [selectedBarberId, setSelectedBarberId] =
    useState("");

  const [selectedServiceId, setSelectedServiceId] =
    useState("");

  const [selectedDate, setSelectedDate] =
    useState(today);

  const [selectedSlot, setSelectedSlot] =
    useState("");

  const [message, setMessage] = useState("");

  async function loadData() {
    const [
      barbersRes,
      servicesRes,
      appointmentsRes,
    ] = await Promise.all([
      fetch(`${API_BASE}/api/barbers`),
      fetch(`${API_BASE}/api/services`),
      fetch(`${API_BASE}/api/appointments`),
    ]);

    setBarbers(await barbersRes.json());
    setServices(await servicesRes.json());
    setAppointments(
      await appointmentsRes.json()
    );
  }

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (
      !selectedBarberId ||
      !selectedServiceId ||
      !selectedDate
    ) {
      return;
    }

    async function loadAvailability() {
      const response = await fetch(
        `${API_BASE}/api/availability?barber_id=${selectedBarberId}&service_id=${selectedServiceId}&target_date=${selectedDate}`
      );

      if (!response.ok) {
        setAvailableSlots([]);
        return;
      }

      const data = await response.json();

      setAvailableSlots(data.available_slots || []);
    }

    loadAvailability();
  }, [
    selectedBarberId,
    selectedServiceId,
    selectedDate,
  ]);

  function formatTime(value) {
    return new Date(value).toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit",
    });
  }

  function cleanPhone(phone) {
    return String(phone || "").replace(/\D/g, "");
  }

  const recognizedCustomer = useMemo(() => {
    const phone = cleanPhone(customerPhone);

    if (!phone) {
      return null;
    }

    return appointments.find(
      (appointment) =>
        cleanPhone(
          appointment.customer_phone
        ) === phone
    );
  }, [appointments, customerPhone]);

  useEffect(() => {
    if (
      recognizedCustomer &&
      !customerName
    ) {
      setCustomerName(
        recognizedCustomer.customer_name
      );
    }
  }, [recognizedCustomer]);

  async function createAppointment() {
    if (
      !customerName ||
      !customerPhone ||
      !selectedBarberId ||
      !selectedServiceId ||
      !selectedSlot
    ) {
      setMessage(
        "Please complete all fields."
      );

      return;
    }

    const response = await fetch(
      `${API_BASE}/api/appointments`,
      {
        method: "POST",
        headers: {
          "Content-Type":
            "application/json",
        },
        body: JSON.stringify({
          barber_id: selectedBarberId,
          service_id: selectedServiceId,
          customer_name: customerName,
          customer_phone: customerPhone,
          notes,
          start_datetime: selectedSlot,
        }),
      }
    );

    if (response.ok) {
      setMessage(
        "Appointment booked successfully."
      );

      setSelectedSlot("");
      setNotes("");

      loadData();
    } else {
      setMessage(
        "Could not create appointment."
      );
    }
  }

  return (
    <main className="min-h-screen bg-gray-100 p-4 sm:p-10">
      <div className="max-w-2xl mx-auto space-y-6">
        <section className="bg-white rounded-3xl shadow-lg p-6 border border-gray-200">
          <h1 className="text-5xl font-extrabold tracking-tight">
            ChairTime
          </h1>

          <p className="mt-2 text-gray-900">
            Book your appointment.
          </p>

          {message && (
            <p className="mt-4 font-bold text-green-700">
              {message}
            </p>
          )}
        </section>

        <section className="bg-white rounded-3xl shadow-lg p-6 border border-gray-200 space-y-5">
          <div>
            <label className="block font-bold mb-2">
              Phone Number
            </label>

            <input
              className="w-full border rounded-2xl p-5 text-xl"
              value={customerPhone}
              onChange={(e) =>
                setCustomerPhone(
                  e.target.value
                )
              }
              placeholder="240-555-1234"
            />

            {recognizedCustomer && (
              <p className="mt-2 text-green-700 font-bold">
                Welcome back,
                {" "}
                {
                  recognizedCustomer.customer_name
                }
                .
              </p>
            )}
          </div>

          <div>
            <label className="block font-bold mb-2">
              Name
            </label>

            <input
              className="w-full border rounded-2xl p-5 text-xl"
              value={customerName}
              onChange={(e) =>
                setCustomerName(
                  e.target.value
                )
              }
              placeholder="Your name"
            />
          </div>

          <div>
            <label className="block font-bold mb-2">
              Barber
            </label>

            <select
              className="w-full border rounded-2xl p-5 text-xl"
              value={selectedBarberId}
              onChange={(e) =>
                setSelectedBarberId(
                  e.target.value
                )
              }
            >
              <option value="">
                Select barber
              </option>

              {barbers.map((barber) => (
                <option
                  key={barber.id}
                  value={barber.id}
                >
                  {barber.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block font-bold mb-2">
              Service
            </label>

            <select
              className="w-full border rounded-2xl p-5 text-xl"
              value={selectedServiceId}
              onChange={(e) =>
                setSelectedServiceId(
                  e.target.value
                )
              }
            >
              <option value="">
                Select service
              </option>

              {services.map((service) => (
                <option
                  key={service.id}
                  value={service.id}
                >
                  {service.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block font-bold mb-2">
              Date
            </label>

            <input
              type="date"
              className="w-full border rounded-2xl p-5 text-xl"
              value={selectedDate}
              onChange={(e) =>
                setSelectedDate(
                  e.target.value
                )
              }
            />
          </div>

          <div>
            <label className="block font-bold mb-2">
              Available Times
            </label>

            <div className="grid grid-cols-2 gap-3">
              {availableSlots.map((slot) => (
                <button
                  key={slot}
                  onClick={() =>
                    setSelectedSlot(slot)
                  }
                  className={`rounded-2xl p-4 font-bold border ${
                    selectedSlot === slot
                      ? "bg-black text-white"
                      : "bg-white"
                  }`}
                >
                  {formatTime(slot)}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block font-bold mb-2">
              Notes
            </label>

            <textarea
              className="w-full border rounded-2xl p-5 min-h-28"
              value={notes}
              onChange={(e) =>
                setNotes(e.target.value)
              }
              placeholder="Optional notes"
            />
          </div>

          <button
            onClick={createAppointment}
            className="w-full bg-black text-white rounded-2xl p-5 text-xl font-bold"
          >
            Book Appointment
          </button>
        </section>
      </div>
    </main>
  );
}