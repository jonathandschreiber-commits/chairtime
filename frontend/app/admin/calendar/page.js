"use client";

import { useEffect, useMemo, useState } from "react";

const API_BASE = "https://chairtime-production-94da.up.railway.app";

const HOURS = [
  "08:00", "09:00", "10:00", "11:00", "12:00", "13:00",
  "14:00", "15:00", "16:00", "17:00", "18:00", "19:00",
];

const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

export default function CalendarPage() {
  const today = new Date().toISOString().slice(0, 10);

  const [appointments, setAppointments] = useState([]);
  const [barbers, setBarbers] = useState([]);
  const [services, setServices] = useState([]);
  const [blockedTimes, setBlockedTimes] = useState([]);

  const [selectedDate, setSelectedDate] = useState(today);
  const [selectedBarberId, setSelectedBarberId] = useState("");
  const [viewMode, setViewMode] = useState("day");
  const [message, setMessage] = useState("");

  const [movingAppointment, setMovingAppointment] = useState(null);
  const [moveDate, setMoveDate] = useState(today);
  const [moveTime, setMoveTime] = useState("09:00");

  async function loadData() {
    const [appointmentsRes, barbersRes, servicesRes, blockedRes] =
      await Promise.all([
        fetch(`${API_BASE}/api/appointments`),
        fetch(`${API_BASE}/api/barbers`),
        fetch(`${API_BASE}/api/services`),
        fetch(`${API_BASE}/api/blocked-times`),
      ]);

    const barbersData = await barbersRes.json();

    setAppointments(await appointmentsRes.json());
    setBarbers(barbersData);
    setServices(await servicesRes.json());
    setBlockedTimes(await blockedRes.json());

    if (barbersData.length > 0 && !selectedBarberId) {
      setSelectedBarberId(barbersData[0].id);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  function serviceName(id) {
    return services.find((service) => service.id === id)?.name || "Service";
  }

  function sameDay(value, date) {
    return new Date(value).toISOString().slice(0, 10) === date;
  }

  function formatTime(value) {
    return new Date(value).toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit",
    });
  }

  function getWeekDates(dateString) {
    const date = new Date(`${dateString}T12:00:00`);
    const day = date.getDay();
    const sunday = new Date(date);
    sunday.setDate(date.getDate() - day);

    return Array.from({ length: 7 }, (_, index) => {
      const d = new Date(sunday);
      d.setDate(sunday.getDate() + index);
      return d.toISOString().slice(0, 10);
    });
  }

  async function updateAppointmentStatus(appointmentId, status) {
    const response = await fetch(
      `${API_BASE}/api/appointments/${appointmentId}/status?status=${status}`,
      { method: "PATCH" }
    );

    if (response.ok) {
      setMessage(`Appointment marked ${status}.`);
      loadData();
    } else {
      setMessage("Could not update appointment status.");
    }
  }

  function startMove(appointment) {
    setMovingAppointment(appointment);
    setMoveDate(new Date(appointment.start_datetime).toISOString().slice(0, 10));

    const currentTime = new Date(appointment.start_datetime)
      .toTimeString()
      .slice(0, 5);

    setMoveTime(currentTime);
  }

  async function saveMove() {
    if (!movingAppointment || !moveDate || !moveTime) {
      setMessage("Please choose a new date and time.");
      return;
    }

    const newStart = `${moveDate}T${moveTime}:00`;

    const response = await fetch(
      `${API_BASE}/api/appointments/${movingAppointment.id}/reschedule?new_start_datetime=${encodeURIComponent(newStart)}`,
      { method: "PATCH" }
    );

    if (response.ok) {
      setMessage("Appointment moved.");
      setMovingAppointment(null);
      setSelectedDate(moveDate);
      loadData();
    } else {
      setMessage("Could not move appointment.");
    }
  }

  const selectedBarber = barbers.find((barber) => barber.id === selectedBarberId);

  const dayAppointments = useMemo(() => {
    return appointments
      .filter((appointment) => appointment.barber_id === selectedBarberId)
      .filter((appointment) => sameDay(appointment.start_datetime, selectedDate))
      .sort((a, b) => new Date(a.start_datetime) - new Date(b.start_datetime));
  }, [appointments, selectedBarberId, selectedDate]);

  const dayBlockedTimes = useMemo(() => {
    return blockedTimes
      .filter((block) => block.barber_id === selectedBarberId)
      .filter((block) => sameDay(block.start_datetime, selectedDate))
      .sort((a, b) => new Date(a.start_datetime) - new Date(b.start_datetime));
  }, [blockedTimes, selectedBarberId, selectedDate]);

  const weekDates = getWeekDates(selectedDate);

  function appointmentItemsForHour(hourText) {
    const hour = Number(hourText.split(":")[0]);

    return dayAppointments.filter(
      (appointment) => new Date(appointment.start_datetime).getHours() === hour
    );
  }

  function blockedItemsForHour(hourText) {
    const hour = Number(hourText.split(":")[0]);

    return dayBlockedTimes.filter(
      (block) => new Date(block.start_datetime).getHours() === hour
    );
  }

  function weekItemsForDate(date) {
    const appts = appointments
      .filter((appointment) => appointment.barber_id === selectedBarberId)
      .filter((appointment) => sameDay(appointment.start_datetime, date))
      .map((appointment) => ({
        type: "appointment",
        data: appointment,
        id: appointment.id,
        time: appointment.start_datetime,
        title: appointment.customer_name,
        detail: serviceName(appointment.service_id),
        phone: appointment.customer_phone,
        status: appointment.status,
      }));

    const blocks = blockedTimes
      .filter((block) => block.barber_id === selectedBarberId)
      .filter((block) => sameDay(block.start_datetime, date))
      .map((block) => ({
        type: "blocked",
        id: block.id,
        time: block.start_datetime,
        endTime: block.end_datetime,
        title: block.reason,
        detail: "Blocked Time",
      }));

    return [...appts, ...blocks].sort((a, b) => new Date(a.time) - new Date(b.time));
  }

  function statusButtons(appointment) {
    return (
      <div className="flex flex-wrap gap-2 mt-3">
        <button
          onClick={() => startMove(appointment)}
          className="bg-purple-500 text-white px-3 py-2 rounded-xl text-sm"
        >
          Move
        </button>

        <button
          onClick={() => updateAppointmentStatus(appointment.id, "confirmed")}
          className="bg-blue-400 hover:bg-blue-500 text-white px-3 py-2 rounded-xl text-sm"
        >
          Confirm
        </button>

        <button
          onClick={() => updateAppointmentStatus(appointment.id, "completed")}
          className="bg-green-600 text-white px-3 py-2 rounded-xl text-sm"
        >
          Complete
        </button>

        <button
          onClick={() => updateAppointmentStatus(appointment.id, "no_show")}
          className="bg-yellow-500 text-white px-3 py-2 rounded-xl text-sm"
        >
          No-show
        </button>

        <button
          onClick={() => updateAppointmentStatus(appointment.id, "canceled")}
          className="bg-red-400 hover:bg-red-500 text-white px-3 py-2 rounded-xl text-sm"
        >
          Cancel
        </button>
      </div>
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
            View, move, and manage appointments by barber.
          </p>

          {message && (
            <p className="mt-4 font-semibold text-green-700">{message}</p>
          )}
        </div>

        {movingAppointment && (
          <section className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-gray-200">
            <h2 className="text-3xl font-bold mb-6">Move Appointment</h2>

            <p className="font-semibold mb-4">
              {movingAppointment.customer_name} ·{" "}
              {serviceName(movingAppointment.service_id)}
            </p>

            <div className="grid gap-3 sm:grid-cols-3">
              <input
                type="date"
                className="border rounded-xl p-3"
                value={moveDate}
                onChange={(e) => setMoveDate(e.target.value)}
              />

              <input
                type="time"
                className="border rounded-xl p-3"
                value={moveTime}
                onChange={(e) => setMoveTime(e.target.value)}
              />

              <button
                onClick={saveMove}
                className="bg-black text-white rounded-xl px-6 py-3 font-semibold"
              >
                Save New Time
              </button>
            </div>

            <button
              onClick={() => setMovingAppointment(null)}
              className="mt-4 bg-gray-400 text-white px-4 py-2 rounded-xl"
            >
              Cancel Move
            </button>
          </section>
        )}

        <section className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-gray-200">
          <h2 className="text-3xl font-bold mb-6">Filters</h2>

          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <label className="block font-semibold mb-2">View</label>
              <select
                className="w-full border rounded-xl p-3"
                value={viewMode}
                onChange={(e) => setViewMode(e.target.value)}
              >
                <option value="day">Day</option>
                <option value="week">Week</option>
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
          </div>
        </section>

        {viewMode === "day" && (
          <section className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-gray-200">
            <h2 className="text-3xl font-bold mb-6">
              Day View — {selectedBarber?.name || "Barber"} — {selectedDate}
            </h2>

            <div className="grid gap-3">
              {HOURS.map((hour) => {
                const appointmentsForHour = appointmentItemsForHour(hour);
                const blockedForHour = blockedItemsForHour(hour);

                return (
                  <div key={hour} className="border rounded-xl p-4">
                    <p className="font-bold mb-3">{hour}</p>

                    {appointmentsForHour.length === 0 && blockedForHour.length === 0 && (
                      <p className="text-gray-900">Open</p>
                    )}

                    <div className="grid gap-2">
                      {appointmentsForHour.map((appointment) => (
                        <div
                          key={appointment.id}
                          className="rounded-xl p-3 bg-blue-100 border border-blue-300"
                        >
                          <p className="font-bold">
                            {formatTime(appointment.start_datetime)} ·{" "}
                            {appointment.customer_name}
                          </p>

                          <p className="text-gray-900">
                            {serviceName(appointment.service_id)}
                          </p>

                          <p className="text-gray-900">
                            {appointment.customer_phone}
                          </p>

                          <p className="text-gray-900">
                            Status: {appointment.status}
                          </p>

                          {statusButtons(appointment)}
                        </div>
                      ))}

                      {blockedForHour.map((block) => (
                        <div
                          key={block.id}
                          className="rounded-xl p-3 bg-gray-200 border border-gray-400"
                        >
                          <p className="font-bold">
                            {formatTime(block.start_datetime)} –{" "}
                            {formatTime(block.end_datetime)}
                          </p>
                          <p className="text-gray-900">Blocked: {block.reason}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {viewMode === "week" && (
          <section className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-gray-200">
            <h2 className="text-3xl font-bold mb-6">
              Week View — {selectedBarber?.name || "Barber"}
            </h2>

            <div className="grid gap-4">
              {weekDates.map((date, index) => {
                const items = weekItemsForDate(date);

                return (
                  <div key={date} className="border rounded-xl p-4">
                    <h3 className="text-xl font-bold mb-3">
                      {DAYS[index]} — {date}
                    </h3>

                    {items.length === 0 && (
                      <p className="text-gray-900">
                        No appointments or blocked time.
                      </p>
                    )}

                    <div className="grid gap-2">
                      {items.map((item) => (
                        <div
                          key={`${item.type}-${item.id}`}
                          className={`rounded-xl p-3 border ${
                            item.type === "appointment"
                              ? "bg-blue-100 border-blue-300"
                              : "bg-gray-200 border-gray-400"
                          }`}
                        >
                          <p className="font-bold">
                            {formatTime(item.time)}
                            {item.endTime ? ` – ${formatTime(item.endTime)}` : ""} ·{" "}
                            {item.title}
                          </p>

                          <p className="text-gray-900">{item.detail}</p>

                          {item.phone && (
                            <p className="text-gray-900">{item.phone}</p>
                          )}

                          {item.status && (
                            <p className="text-gray-900">Status: {item.status}</p>
                          )}

                          {item.type === "appointment" && statusButtons(item.data)}
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}
      </div>
    </main>
  );
}