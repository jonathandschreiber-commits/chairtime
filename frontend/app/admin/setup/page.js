"use client";

import { useEffect, useState } from "react";

const API_BASE = "https://chairtime-production-94da.up.railway.app";

const DAYS = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

export default function SetupPage() {
  const [barbers, setBarbers] = useState([]);
  const [message, setMessage] = useState("");

  const [barberId, setBarberId] = useState("");
  const [weekday, setWeekday] = useState("Monday");
  const [startTime, setStartTime] = useState("09:00");
  const [endTime, setEndTime] = useState("17:00");

  const [blockReason, setBlockReason] = useState("Lunch");
  const [blockStart, setBlockStart] = useState("");
  const [blockEnd, setBlockEnd] = useState("");
  const [fullDayDate, setFullDayDate] = useState("");

  async function loadBarbers() {
    const response = await fetch(API_BASE + "/api/barbers");
    const data = await response.json();

    setBarbers(data);

    if (data.length > 0 && !barberId) {
      setBarberId(data[0].id);
    }
  }

  useEffect(() => {
    loadBarbers();
  }, []);

  async function saveAvailability() {
    const dayIndex = DAYS.indexOf(weekday);

    const response = await fetch(API_BASE + "/api/availability-rules", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        barber_id: barberId,
        weekday: dayIndex,
        start_time: startTime + ":00",
        end_time: endTime + ":00",
      }),
    });

    if (response.ok) {
      setMessage("Availability saved.");
    }
  }

  async function blockTime() {
    const response = await fetch(API_BASE + "/api/blocked-times", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        barber_id: barberId,
        reason: blockReason,
        start_datetime: blockStart,
        end_datetime: blockEnd,
      }),
    });

    if (response.ok) {
      setMessage("Time blocked.");
    }
  }

  async function blockFullDay(reason) {
    const response = await fetch(API_BASE + "/api/blocked-times", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        barber_id: barberId,
        reason,
        start_datetime: fullDayDate + "T00:00:00",
        end_datetime: fullDayDate + "T23:59:00",
      }),
    });

    if (response.ok) {
      setMessage(reason + " saved.");
    }
  }

  return (
    <main className="min-h-screen bg-gray-100 p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        <h1 className="text-4xl font-bold">Shop Setup</h1>

        {message && (
          <div className="bg-green-100 p-3 rounded-xl font-bold">
            {message}
          </div>
        )}

        <div className="bg-white p-6 rounded-2xl shadow space-y-4">
          <h2 className="text-2xl font-bold">Weekly Availability</h2>

          <select
            value={barberId}
            onChange={(e) => setBarberId(e.target.value)}
            className="border p-3 rounded w-full"
          >
            {barbers.map((barber) => (
              <option key={barber.id} value={barber.id}>
                {barber.name}
              </option>
            ))}
          </select>

          <select
            value={weekday}
            onChange={(e) => setWeekday(e.target.value)}
            className="border p-3 rounded w-full"
          >
            {DAYS.map((day) => (
              <option key={day}>{day}</option>
            ))}
          </select>

          <input
            type="time"
            value={startTime}
            onChange={(e) => setStartTime(e.target.value)}
            className="border p-3 rounded w-full"
          />

          <input
            type="time"
            value={endTime}
            onChange={(e) => setEndTime(e.target.value)}
            className="border p-3 rounded w-full"
          />

          <button
            onClick={saveAvailability}
            className="bg-black text-white px-4 py-3 rounded-xl"
          >
            Save Availability
          </button>
        </div>

        <div className="bg-white p-6 rounded-2xl shadow space-y-4">
          <h2 className="text-2xl font-bold">Quick Block Time</h2>

          <input
            value={blockReason}
            onChange={(e) => setBlockReason(e.target.value)}
            className="border p-3 rounded w-full"
          />

          <input
            type="datetime-local"
            value={blockStart}
            onChange={(e) => setBlockStart(e.target.value)}
            className="border p-3 rounded w-full"
          />

          <input
            type="datetime-local"
            value={blockEnd}
            onChange={(e) => setBlockEnd(e.target.value)}
            className="border p-3 rounded w-full"
          />

          <button
            onClick={blockTime}
            className="bg-black text-white px-4 py-3 rounded-xl"
          >
            Block Time
          </button>
        </div>

        <div className="bg-white p-6 rounded-2xl shadow space-y-4">
          <h2 className="text-2xl font-bold">Full Day Block</h2>

          <input
            type="date"
            value={fullDayDate}
            onChange={(e) => setFullDayDate(e.target.value)}
            className="border p-3 rounded w-full"
          />

          <div className="flex gap-3">
            <button
              onClick={() => blockFullDay("Vacation")}
              className="bg-black text-white px-4 py-3 rounded-xl"
            >
              Vacation
            </button>

            <button
              onClick={() => blockFullDay("Closed")}
              className="bg-red-600 text-white px-4 py-3 rounded-xl"
            >
              Closed
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}