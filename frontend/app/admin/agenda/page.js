"use client";

import { useEffect, useMemo, useState } from "react";

const API_BASE = "https://chairtime-production-94da.up.railway.app";

const STATUS_LABELS = {
  confirmed: "Confirmed",
  completed: "Done",
  no_show: "No-show",
  canceled: "Canceled",
};

const STATUS_STYLES = {
  confirmed: "bg-blue-100 border-blue-300",
  completed: "bg-green-100 border-green-300",
  no_show: "bg-yellow-100 border-yellow-300",
  canceled: "bg-red-100 border-red-300",
};

export default function AgendaPage() {
  const today = new Date().toISOString().slice(0, 10);

  const [appointments, setAppointments] = useState([]);
  const [barbers, setBarbers] = useState([]);
  const [services, setServices] = useState([]);
  const [selectedDate, setSelectedDate] = useState(today);
  const [selectedBarberId, setSelectedBarberId] = useState("");
  const [message, setMessage] = useState("");

  async function loadData() {
    const [appointmentsRes, barbersRes, servicesRes] = await Promise.all([
      fetch(`${API_BASE}/api/appointments`),
      fetch(`${API_BASE}/api/barbers`),
      fetch(`${API_BASE}/api/services`),
    ]);

    setAppointments(await appointmentsRes.json());
    setBarbers(await barbersRes.json());
    setServices(await servicesRes.json());
  }

  useEffect(() => {
    loadData();
  }, []);

  function sameDay(value, date) {
    return new Date(value).toISOString().slice(0, 10) === date;
  }

  function formatTime(value) {
    return new Date(value).toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit",
    });
  }

  function barberName(id) {
    return barbers.find((barber) => barber.id === id)?.name || "Barber";
  }

  function serviceName(id) {
    return services.find((service) => service.id === id)?.name || "Service";
  }

  async function updateStatus(appointmentId, status) {
    const response = await fetch(
      `${API_BASE}/api/appointments/${appointmentId}/status?status=${status}`,
      { method: "PATCH" }
    );

    if (response.ok) {
      setMessage(`Marked ${STATUS_LABELS[status]}.`);
      loadData();
    } else {
      setMessage("Could not update appointment.");
    }
  }

  const agendaAppointments = useMemo(() => {
    return appointments
      .filter((appointment) => sameDay(appointment.start_datetime, selectedDate))
      .filter((appointment) =>
        selectedBarberId ? appointment.barber_id === selectedBarberId : true
      )
      .sort((a, b) => new Date(a.start_datetime) - new Date(b.start_datetime));
  }, [appointments, selectedDate, selectedBarberId]);

  return (
    <main className="min-h-screen bg-gray-100 p-4 sm:p-8">
      <div className="max-w-4xl mx-auto space-y-6">
        <section className="bg-white rounded-3xl shadow-lg p-6 border border-gray-200">
          <h1 className="text-5xl font-extrabold tracking-tight mb-2">
            Daily Agenda
          </h1>

          <p className="text-gray-900">
            Today’s appointments. Simple and fast.
          </p>

          {message && (
            <p className="mt-4 font-bold text-green-700">
              {message}
            </p>
          )}
        </section>

        <section className="bg-white rounded-3xl shadow-lg p-6 border border-gray-200">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="block font-bold mb-2">Date</label>
              <input
                type="date"
                className="w-full border rounded-xl p-4 text-lg"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
              />
            </div>

            <div>
              <label className="block font-bold mb-2">Barber</label>
              <select
                className="w-full border rounded-xl p-4 text-lg"
                value={selectedBarberId}
                onChange={(e) => setSelectedBarberId(e.target.value)}
              >
                <option value="">All barbers</option>
                {barbers.map((barber) => (
                  <option key={barber.id} value={barber.id}>
                    {barber.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          {agendaAppointments.length === 0 && (
            <div className="bg-white rounded-3xl shadow-lg p-6 border border-gray-200">
              <p className="text-2xl font-bold">No appointments.</p>
            </div>
          )}

          {agendaAppointments.map((appointment) => {
            const statusStyle =
              STATUS_STYLES[appointment.status] || STATUS_STYLES.confirmed;

            const statusLabel =
              STATUS_LABELS[appointment.status] || "Confirmed";

            return (
              <div
                key={appointment.id}
                className={`rounded-3xl shadow-lg p-6 border ${statusStyle}`}
              >
                <div className="flex justify-between gap-4">
                  <div>
                    <p className="text-4xl font-extrabold">
                      {formatTime(appointment.start_datetime)}
                    </p>

                    <p className="text-2xl font-bold mt-2">
                      {appointment.customer_name}
                    </p>

                    <p className="text-lg text-gray-900">
                      {serviceName(appointment.service_id)} ·{" "}
                      {barberName(appointment.barber_id)}
                    </p>

                    <a
                      className="inline-block mt-3 text-lg font-bold underline"
                      href={`tel:${appointment.customer_phone}`}
                    >
                      Call {appointment.customer_phone}
                    </a>
                  </div>

                  <div>
                    <span className="font-bold bg-white border rounded-full px-3 py-1">
                      {statusLabel}
                    </span>
                  </div>
                </div>

                {appointment.notes && (
                  <div className="mt-4 bg-white border rounded-2xl p-4">
                    <p className="font-bold">Notes</p>
                    <p className="text-gray-900">{appointment.notes}</p>
                  </div>
                )}

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-5">
                  <button
                    onClick={() => updateStatus(appointment.id, "confirmed")}
                    className="bg-blue-500 text-white rounded-xl p-4 font-bold"
                  >
                    Confirm
                  </button>

                  <button
                    onClick={() => updateStatus(appointment.id, "completed")}
                    className="bg-green-600 text-white rounded-xl p-4 font-bold"
                  >
                    Done
                  </button>

                  <button
                    onClick={() => updateStatus(appointment.id, "no_show")}
                    className="bg-yellow-500 text-white rounded-xl p-4 font-bold"
                  >
                    No-show
                  </button>

                  <button
                    onClick={() => updateStatus(appointment.id, "canceled")}
                    className="bg-red-500 text-white rounded-xl p-4 font-bold"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            );
          })}
        </section>
      </div>
    </main>
  );
}