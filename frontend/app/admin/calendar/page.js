"use client";

import { useEffect, useMemo, useState } from "react";

const API_BASE = "https://chairtime-production-94da.up.railway.app";

export default function CalendarPage() {
  const today = new Date().toISOString().slice(0, 10);

  const [appointments, setAppointments] = useState([]);
  const [barbers, setBarbers] = useState([]);
  const [services, setServices] = useState([]);
  const [blockedTimes, setBlockedTimes] = useState([]);

  const [selectedDate, setSelectedDate] = useState(today);
  const [selectedBarberId, setSelectedBarberId] = useState("all");

  async function loadData() {
    const [appointmentsRes, barbersRes, servicesRes, blockedRes] =
      await Promise.all([
        fetch(`${API_BASE}/api/appointments`),
        fetch(`${API_BASE}/api/barbers`),
        fetch(`${API_BASE}/api/services`),
        fetch(`${API_BASE}/api/blocked-times`),
      ]);

    setAppointments(await appointmentsRes.json());
    setBarbers(await barbersRes.json());
    setServices(await servicesRes.json());
    setBlockedTimes(await blockedRes.json());
  }

  useEffect(() => {
    loadData();
  }, []);

  function barberName(id) {
    return barbers.find((barber) => barber.id === id)?.name || "Barber";
  }

  function serviceName(id) {
    return services.find((service) => service.id === id)?.name || "Service";
  }

  function sameDay(value) {
    return new Date(value).toISOString().slice(0, 10) === selectedDate;
  }

  const filteredAppointments = useMemo(() => {
    return appointments
      .filter((appointment) => sameDay(appointment.start_datetime))
      .filter(
        (appointment) =>
          selectedBarberId === "all" ||
          appointment.barber_id === selectedBarberId
      )
      .sort(
        (a, b) =>
          new Date(a.start_datetime).getTime() -
          new Date(b.start_datetime).getTime()
      );
  }, [appointments, selectedDate, selectedBarberId]);

  const filteredBlockedTimes = useMemo(() => {
    return blockedTimes
      .filter((block) => sameDay(block.start_datetime))
      .filter(
        (block) =>
          selectedBarberId === "all" || block.barber_id === selectedBarberId
      )
      .sort(
        (a, b) =>
          new Date(a.start_datetime).getTime() -
          new Date(b.start_datetime).getTime()
      );
  }, [blockedTimes, selectedDate, selectedBarberId]);

  return (
    <main className="min-h-screen bg-gray-100 p-4 sm:p-10">
      <div className="max-w-6xl mx-auto space-y-8">
        <div className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-gray-200">
          <h1 className="text-5xl font-extrabold tracking-tight mb-3">
            ChairTime Calendar
          </h1>

          <p className="text-gray-900">
            Filter appointments and blocked time by date and barber.
          </p>
        </div>

        <section className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-gray-200">
          <h2 className="text-3xl font-bold mb-6">Filters</h2>

          <div className="grid gap-4 sm:grid-cols-2">
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
              <label className="block font-semibold mb-2">Barber</label>
              <select
                className="w-full border rounded-xl p-3"
                value={selectedBarberId}
                onChange={(e) => setSelectedBarberId(e.target.value)}
              >
                <option value="all">All Staff</option>

                {barbers.map((barber) => (
                  <option key={barber.id} value={barber.id}>
                    {barber.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </section>

        <section className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-gray-200">
          <h2 className="text-3xl font-bold mb-6">
            Appointments for {selectedDate}
          </h2>

          <div className="grid gap-3">
            {filteredAppointments.length === 0 && (
              <p className="text-gray-900">
                No appointments for this date and barber filter.
              </p>
            )}

            {filteredAppointments.map((appointment) => (
              <div key={appointment.id} className="border rounded-xl p-4">
                <p className="font-semibold">
                  {new Date(appointment.start_datetime).toLocaleTimeString([], {
                    hour: "numeric",
                    minute: "2-digit",
                  })}{" "}
                  — {appointment.customer_name}
                </p>

                <p className="text-gray-900">
                  {barberName(appointment.barber_id)} ·{" "}
                  {serviceName(appointment.service_id)}
                </p>

                <p className="text-gray-900">
                  Phone: {appointment.customer_phone}
                </p>

                <p className="text-gray-900">Status: {appointment.status}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-gray-200">
          <h2 className="text-3xl font-bold mb-6">
            Blocked Time for {selectedDate}
          </h2>

          <div className="grid gap-3">
            {filteredBlockedTimes.length === 0 && (
              <p className="text-gray-900">
                No blocked time for this date and barber filter.
              </p>
            )}

            {filteredBlockedTimes.map((block) => (
              <div key={block.id} className="border rounded-xl p-4 bg-gray-100">
                <p className="font-semibold">
                  {new Date(block.start_datetime).toLocaleTimeString([], {
                    hour: "numeric",
                    minute: "2-digit",
                  })}{" "}
                  –{" "}
                  {new Date(block.end_datetime).toLocaleTimeString([], {
                    hour: "numeric",
                    minute: "2-digit",
                  })}{" "}
                  · {block.reason}
                </p>

                <p className="text-gray-900">{barberName(block.barber_id)}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}