"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

const API_BASE = "https://chairtime-production-94da.up.railway.app";

export default function ShopBookingPage() {
  const params = useParams();

  const SHOP_SLUG = Array.isArray(params?.shop)
    ? params.shop[0]
    : params?.shop || "";

  const today = new Date().toISOString().slice(0, 10);

  const [barbers, setBarbers] = useState([]);
  const [services, setServices] = useState([]);
  const [appointments, setAppointments] = useState([]);
  const [availableSlots, setAvailableSlots] = useState([]);

  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [notes, setNotes] = useState("");

  const [selectedBarberId, setSelectedBarberId] = useState("");
  const [selectedServiceId, setSelectedServiceId] = useState("");
  const [selectedDate, setSelectedDate] = useState(today);
  const [selectedSlot, setSelectedSlot] = useState("");

  const [message, setMessage] = useState("");
  const [booking, setBooking] = useState(false);

  async function loadData() {
    if (!SHOP_SLUG) {
      return;
    }

    try {
      const query = `?shop_slug=${encodeURIComponent(SHOP_SLUG)}`;

      const [barbersRes, servicesRes, appointmentsRes] =
        await Promise.all([
          fetch(`${API_BASE}/api/barbers${query}`),
          fetch(`${API_BASE}/api/services${query}`),
          fetch(`${API_BASE}/api/appointments${query}`),
        ]);

      if (barbersRes.ok) {
        setBarbers(await barbersRes.json());
      }

      if (servicesRes.ok) {
        setServices(await servicesRes.json());
      }

      if (appointmentsRes.ok) {
        setAppointments(await appointmentsRes.json());
      }
    } catch (error) {
      console.error("Could not load booking data:", error);
    }
  }

  useEffect(() => {
    loadData();
  }, [SHOP_SLUG]);

  function cleanPhone(phone) {
    return String(phone || "").replace(/\D/g, "");
  }

  const recognizedCustomer = useMemo(() => {
    const phone = cleanPhone(customerPhone);

    if (!phone || !SHOP_SLUG) {
      return null;
    }

    return (
      appointments
        .filter(
          (appointment) =>
            appointment.shop_slug === SHOP_SLUG &&
            cleanPhone(appointment.customer_phone) === phone
        )
        .sort(
          (a, b) =>
            new Date(b.start_datetime) -
            new Date(a.start_datetime)
        )[0] || null
    );
  }, [appointments, customerPhone, SHOP_SLUG]);

  useEffect(() => {
    if (!recognizedCustomer) {
      return;
    }

    if (!customerName) {
      setCustomerName(recognizedCustomer.customer_name);
    }

    if (recognizedCustomer.barber_id) {
      setSelectedBarberId(recognizedCustomer.barber_id);
    }

    if (recognizedCustomer.service_id) {
      setSelectedServiceId(recognizedCustomer.service_id);
    }
  }, [recognizedCustomer, customerName]);

  useEffect(() => {
    if (
      !SHOP_SLUG ||
      !selectedBarberId ||
      !selectedServiceId ||
      !selectedDate
    ) {
      setAvailableSlots([]);
      setSelectedSlot("");
      return;
    }

    async function loadAvailability() {
      setSelectedSlot("");

      try {
        const params = new URLSearchParams({
          shop_slug: SHOP_SLUG,
          barber_id: selectedBarberId,
          service_id: selectedServiceId,
          target_date: selectedDate,
        });

        const response = await fetch(
          `${API_BASE}/api/availability?${params.toString()}`
        );

        if (!response.ok) {
          setAvailableSlots([]);
          return;
        }

        const data = await response.json();

        setAvailableSlots(data.slots || []);
      } catch (error) {
        console.error("Could not load availability:", error);
        setAvailableSlots([]);
      }
    }

    loadAvailability();
  }, [
    SHOP_SLUG,
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

  function barberName(id) {
    return barbers.find((barber) => barber.id === id)?.name || "staff member";
  }

  function serviceName(id) {
    return services.find((service) => service.id === id)?.name || "service";
  }

  async function createAppointment() {
    if (
      !customerName.trim() ||
      !customerPhone.trim() ||
      !selectedBarberId ||
      !selectedServiceId ||
      !selectedSlot
    ) {
      setMessage("Please complete all fields.");
      return;
    }

    setBooking(true);
    setMessage("");

    try {
      const response = await fetch(`${API_BASE}/api/appointments`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          shop_slug: SHOP_SLUG,
          barber_id: selectedBarberId,
          service_id: selectedServiceId,
          customer_name: customerName.trim(),
          customer_phone: customerPhone.trim(),
          notes: notes.trim() || null,
          start_datetime: selectedSlot,
        }),
      });

      if (response.ok) {
        setMessage("Appointment booked successfully.");
        setSelectedSlot("");
        setNotes("");
        await loadData();
      } else {
        let detail = "";

        try {
          const errorData = await response.json();

          detail =
            typeof errorData.detail === "string"
              ? errorData.detail
              : "";
        } catch {
          // Keep the simple customer-facing message below.
        }

        console.error(
          "Appointment creation failed:",
          response.status,
          detail
        );

        setMessage(
          detail || "Could not create appointment."
        );
      }
    } catch (error) {
      console.error("Could not create appointment:", error);
      setMessage("Could not create appointment.");
    } finally {
      setBooking(false);
    }
  }

  return (
    <main className="min-h-screen bg-gray-100 p-4 sm:p-10">
      <div className="max-w-2xl mx-auto space-y-6">
        <section className="bg-white rounded-3xl shadow-lg p-6 border border-gray-200">
          <h1 className="text-5xl font-extrabold tracking-tight">
            Book an Appointment
          </h1>

          <p className="mt-2 text-gray-900">
            Choose your service, staff member, date, and time.
          </p>

          {message && (
            <p
              className={`mt-4 font-bold ${
                message === "Appointment booked successfully."
                  ? "text-green-700"
                  : "text-red-700"
              }`}
            >
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
              onChange={(event) =>
                setCustomerPhone(event.target.value)
              }
              placeholder="240-555-1234"
            />

            {recognizedCustomer && (
              <p className="mt-2 text-green-700 font-bold">
                Welcome back, {recognizedCustomer.customer_name}. We selected{" "}
                {barberName(recognizedCustomer.barber_id)} and{" "}
                {serviceName(recognizedCustomer.service_id)} from your last visit.
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
              onChange={(event) =>
                setCustomerName(event.target.value)
              }
              placeholder="Your name"
            />
          </div>

          <div>
            <label className="block font-bold mb-2">
              Staff Member
            </label>

            <select
              className="w-full border rounded-2xl p-5 text-xl"
              value={selectedBarberId}
              onChange={(event) => {
                setSelectedBarberId(event.target.value);
                setSelectedSlot("");
              }}
            >
              <option value="">Select staff member</option>

              {barbers.map((barber) => (
                <option key={barber.id} value={barber.id}>
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
              onChange={(event) => {
                setSelectedServiceId(event.target.value);
                setSelectedSlot("");
              }}
            >
              <option value="">Select service</option>

              {services.map((service) => (
                <option key={service.id} value={service.id}>
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
              min={today}
              className="w-full border rounded-2xl p-5 text-xl"
              value={selectedDate}
              onChange={(event) => {
                setSelectedDate(event.target.value);
                setSelectedSlot("");
              }}
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
                  type="button"
                  onClick={() => setSelectedSlot(slot)}
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

            {availableSlots.length === 0 && (
              <p className="mt-3 text-gray-900">
                Choose a staff member, service, and date to see times.
              </p>
            )}
          </div>

          <div>
            <label className="block font-bold mb-2">
              Notes
            </label>

            <textarea
              className="w-full border rounded-2xl p-5 min-h-28"
              value={notes}
              onChange={(event) =>
                setNotes(event.target.value)
              }
              placeholder="Optional notes"
            />
          </div>

          <button
            type="button"
            onClick={createAppointment}
            disabled={booking}
            className="w-full bg-black text-white rounded-2xl p-5 text-xl font-bold disabled:opacity-50"
          >
            {booking ? "Booking..." : "Book Appointment"}
          </button>
        </section>
      </div>
    </main>
  );
}
