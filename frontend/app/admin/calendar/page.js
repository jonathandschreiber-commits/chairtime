"use client";

import { useEffect, useMemo, useState } from "react";

const API_BASE = "https://chairtime-production-94da.up.railway.app";

const HOURS = [
  "08:00",
  "09:00",
  "10:00",
  "11:00",
  "12:00",
  "13:00",
  "14:00",
  "15:00",
  "16:00",
  "17:00",
  "18:00",
  "19:00",
];

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

  function timeHour(value) {
    return new Date(value).getHours();
  }

  function formatTime(value) {
    return new Date(value).toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit",
    });
  }

  const visibleBarbers = useMemo(() => {
    if (selectedBarberId === "all") {
      return barbers;
    }

    return barbers.filter((barber) => barber.id === selectedBarberId);
  }, [barbers, selectedBarberId]);

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

  function appointmentItems(barberId, hourText) {
    const hour = Number(hourText.split(":")[0]);

    return filteredAppointments.filter(
      (appointment) =>
        appointment.barber_id === barberId &&
        timeHour(appointment.start_datetime) === hour
    );
  }

  function blockedItems(barberId, hourText) {
    const hour = Number(hourText.split(":")[0]);

    return filteredBlockedTimes.filter(
      (block) =>
        block.barber_id === barberId &&
        timeHour(block.start_datetime) === hour
    );
  }

  return (
    <main className="min-h-screen bg-gray-100 p-4 sm:p-10">
      <div className="max-w-7xl mx-auto space-y-8">
        <div className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-gray-200">
          <h1 className="text-5xl font-extrabold tracking-tight mb-3">
            ChairTime Calendar
          </h1>

          <p className="text-gray-900">
            Daily schedule view by barber, appointment, and blocked time.
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

        <section className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-gray-200 overflow-x-auto">
          <h2 className="text-3xl font-bold mb-6">
            Day View for {selectedDate}
          </h2>

          <div className="min-w-[900px]">
            <div
              className="grid border-b font-bold"
              style={{
                gridTemplateColumns: `100px repeat(${visibleBarbers.length}, minmax(160px, 1fr))`,
              }}
            >
              <div className="p-3">Time</div>

              {visibleBarbers.map((barber) => (
                <div key={barber.id} className="p-3 border-l">
                  {barber.name}
                </div>
              ))}
            </div>

            {HOURS.map((hour) => (
              <div
                key={hour}
                className="grid border-b min-h-[90px]"
                style={{
                  gridTemplateColumns: `100px repeat(${visibleBarbers.length}, minmax(160px, 1fr))`,
                }}
              >
                <div className="p-3 font-semibold bg-gray-50">
                  {hour}
                </div>

                {visibleBarbers.map((barber) => {
                  const appointmentsForCell = appointmentItems(
                    barber.id,
                    hour
                  );
                  const blockedForCell = blockedItems(barber.id, hour);

                  return (
                    <div key={barber.id} className="p-2 border-l space-y-2">
                      {appointmentsForCell.map((appointment) => (
                        <div
                          key={appointment.id}
                          className="rounded-xl p-3 bg-blue-100 border border-blue-300"
                        >
                          <p className="font-bold">
                            {formatTime(appointment.start_datetime)} ·{" "}
                            {appointment.customer_name}
                          </p>

                          <p className="text-sm text-gray-900">
                            {serviceName(appointment.service_id)}
                          </p>

                          <p className="text-sm text-gray-900">
                            {appointment.customer_phone}
                          </p>
                        </div>
                      ))}

                      {blockedForCell.map((block) => (
                        <div
                          key={block.id}
                          className="rounded-xl p-3 bg-gray-200 border border-gray-400"
                        >
                          <p className="font-bold">
                            {formatTime(block.start_datetime)} –{" "}
                            {formatTime(block.end_datetime)}
                          </p>

                          <p className="text-sm text-gray-900">
                            Blocked: {block.reason}
                          </p>
                        </div>
                      ))}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </section>

        <section className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-gray-200">
          <h2 className="text-3xl font-bold mb-6">Summary</h2>

          <p className="text-gray-900">
            {filteredAppointments.length} appointments and{" "}
            {filteredBlockedTimes.length} blocked times for the selected
            filters.
          </p>
        </section>
      </div>
    </main>
  );
}