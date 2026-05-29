"use client";

import { useEffect, useMemo, useState } from "react";

const API_BASE = "https://chairtime-production-94da.up.railway.app";

const HOURS = [
  "08:00", "09:00", "10:00", "11:00", "12:00", "13:00",
  "14:00", "15:00", "16:00", "17:00", "18:00", "19:00",
];

const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

const STATUS_STYLES = {
  confirmed: "bg-blue-100 border-blue-300",
  completed: "bg-green-100 border-green-300",
  no_show: "bg-yellow-100 border-yellow-300",
  canceled: "bg-red-100 border-red-300",
};

const STATUS_LABELS = {
  confirmed: "Confirmed",
  completed: "Completed",
  no_show: "No-show",
  canceled: "Canceled",
};

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

  const [movingAppointmentId, setMovingAppointmentId] = useState("");
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

  function startMove(appointment) {
    setMovingAppointmentId(appointment.id);
    setMoveDate(new Date(appointment.start_datetime).toISOString().slice(0, 10));
    setMoveTime(new Date(appointment.start_datetime).toTimeString().slice(0, 5));
    setMessage("");
  }

  async function saveMove(appointment) {
    const newStart = `${moveDate}T${moveTime}:00`;

    const response = await fetch(
      `${API_BASE}/api/appointments/${appointment.id}/reschedule?new_start_datetime=${encodeURIComponent(newStart)}`,
      { method: "PATCH" }
    );

    if (response.ok) {
      setMessage("Appointment moved.");
      setMovingAppointmentId("");
      setSelectedDate(moveDate);
      loadData();
    } else {
      setMessage("Could not move appointment. That time may already be booked or blocked.");
    }
  }

  async function updateAppointmentStatus(appointmentId, status) {
    const response = await fetch(
      `${API_BASE}/api/appointments/${appointmentId}/status?status=${status}`,
      { method: "PATCH" }
    );

    if (response.ok) {
      setMessage(`Appointment marked ${STATUS_LABELS[status]}.`);
      loadData();
    } else {
      setMessage("Could not update appointment status.");
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
      }));

    return [...appts, ...blocks].sort((a, b) => new Date(a.time) - new Date(b.time));
  }

  function appointmentCard(appointment) {
    const isMoving = movingAppointmentId === appointment.id;
    const statusStyle = STATUS_STYLES[appointment.status] || STATUS_STYLES.confirmed;
    const statusLabel = STATUS_LABELS[appointment.status] || "Confirmed";

    return (
      <div key={appointment.id} className={`rounded-xl p-4 border ${statusStyle}`}>
        <div className="flex justify-between gap-3 items-start">
          <div>
            <p className="font-bold text-lg">
              {formatTime(appointment.start_datetime)} · {appointment.customer_name}
            </p>

            <p className="text-gray-900">{serviceName(appointment.service_id)}</p>
            <p className="text-gray-900">{appointment.customer_phone}</p>
          </div>

          <span className="font-bold text-sm bg-white border rounded-full px-3 py-1">
            {statusLabel}
          </span>
        </div>

        {!isMoving && (
          <div className="flex flex-wrap gap-2 mt-4">
            <button onClick={() => startMove(appointment)} className="bg-purple-500 text-white px-3 py-2 rounded-xl text-sm">
              Move
            </button>

            <button onClick={() => updateAppointmentStatus(appointment.id, "confirmed")} className="bg-blue-400 hover:bg-blue-500 text-white px-3 py-2 rounded-xl text-sm">
              Confirm
            </button>

            <button onClick={() => updateAppointmentStatus(appointment.id, "completed")} className="bg-green-600 text-white px-3 py-2 rounded-xl text-sm">
              Complete
            </button>

            <button onClick={() => updateAppointmentStatus(appointment.id, "no_show")} className="bg-yellow-500 text-white px-3 py-2 rounded-xl text-sm">
              No-show
            </button>

            <button onClick={() => updateAppointmentStatus(appointment.id, "canceled")} className="bg-red-400 hover:bg-red-500 text-white px-3 py-2 rounded-xl text-sm">
              Cancel
            </button>
          </div>
        )}

        {isMoving && (
          <div className="mt-4 bg-white rounded-xl border p-4">
            <p className="font-bold mb-3">Move this appointment</p>

            <div className="grid gap-3 sm:grid-cols-3">
              <input type="date" className="border rounded-xl p-3" value={moveDate} onChange={(e) => setMoveDate(e.target.value)} />
              <input type="time" className="border rounded-xl p-3" value={moveTime} onChange={(e) => setMoveTime(e.target.value)} />

              <button onClick={() => saveMove(appointment)} className="bg-black text-white rounded-xl px-4 py-3 font-semibold">
                Save Move
              </button>
            </div>

            <button onClick={() => setMovingAppointmentId("")} className="mt-3 bg-gray-400 text-white px-4 py-2 rounded-xl">
              Cancel Move
            </button>
          </div>
        )}
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

          {message && <p className="mt-4 font-semibold text-green-700">{message}</p>}
        </div>

        <section className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-gray-200">
          <h2 className="text-3xl font-bold mb-6">Filters</h2>

          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <label className="block font-semibold mb-2">View</label>
              <select className="w-full border rounded-xl p-3" value={viewMode} onChange={(e) => setViewMode(e.target.value)}>
                <option value="day">Day</option>
                <option value="week">Week</option>
              </select>
            </div>

            <div>
              <label className="block font-semibold mb-2">Date</label>
              <input type="date" className="w-full border rounded-xl p-3" value={selectedDate} onChange={(e) => setSelectedDate(e.target.value)} />
            </div>

            <div>
              <label className="block font-semibold mb-2">Barber</label>
              <select className="w-full border rounded-xl p-3" value={selectedBarberId} onChange={(e) => setSelectedBarberId(e.target.value)}>
                {barbers.map((barber) => (
                  <option key={barber.id} value={barber.id}>{barber.name}</option>
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
                      {appointmentsForHour.map((appointment) => appointmentCard(appointment))}

                      {blockedForHour.map((block) => (
                        <div key={block.id} className="rounded-xl p-3 bg-gray-200 border border-gray-400">
                          <p className="font-bold">
                            {formatTime(block.start_datetime)} – {formatTime(block.end_datetime)}
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
                      <p className="text-gray-900">No appointments or blocked time.</p>
                    )}

                    <div className="grid gap-2">
                      {items.map((item) =>
                        item.type === "appointment" ? (
                          appointmentCard(item.data)
                        ) : (
                          <div key={`${item.type}-${item.id}`} className="rounded-xl p-3 border bg-gray-200 border-gray-400">
                            <p className="font-bold">
                              {formatTime(item.time)} – {formatTime(item.endTime)} · {item.title}
                            </p>
                            <p className="text-gray-900">Blocked Time</p>
                          </div>
                        )
                      )}
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