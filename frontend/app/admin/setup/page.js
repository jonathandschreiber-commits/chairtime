"use client";

import { useEffect, useMemo, useState } from "react";

const API_BASE = "https://chairtime-production-94da.up.railway.app";

const WEEKDAY_NAMES = {
  0: "Monday",
  1: "Tuesday",
  2: "Wednesday",
  3: "Thursday",
  4: "Friday",
  5: "Saturday",
  6: "Sunday",
};

const WEEKDAY_MAP = {
  Monday: 0,
  Tuesday: 1,
  Wednesday: 2,
  Thursday: 3,
  Friday: 4,
  Saturday: 5,
  Sunday: 6,
};

export default function SetupPage() {
  const [barbers, setBarbers] = useState([]);
  const [blockedTimes, setBlockedTimes] = useState([]);
  const [availabilityRules, setAvailabilityRules] = useState([]);

  const [availabilityBarberId, setAvailabilityBarberId] = useState("");
  const [availabilityDay, setAvailabilityDay] = useState("Monday");
  const [availabilityStart, setAvailabilityStart] = useState("09:00");
  const [availabilityEnd, setAvailabilityEnd] = useState("17:00");

  const [blockBarberId, setBlockBarberId] = useState("");
  const [blockReason, setBlockReason] = useState("Lunch");
  const [blockStart, setBlockStart] = useState("");
  const [blockEnd, setBlockEnd] = useState("");
  const [fullDayDate, setFullDayDate] = useState(
    new Date().toISOString().slice(0, 10)
  );

  const [message, setMessage] = useState("");

  async function loadData() {
    const [barbersRes, blockedRes, availabilityRes] = await Promise.all([
      fetch(`${API_BASE}/api/barbers`),
      fetch(`${API_BASE}/api/blocked-times`),
      fetch(`${API_BASE}/api/availability-rules`),
    ]);

    const barbersData = await barbersRes.json();

    setBarbers(barbersData);
    setBlockedTimes(await blockedRes.json());
    setAvailabilityRules(await availabilityRes.json());

    if (barbersData.length > 0) {
      if (!availabilityBarberId) setAvailabilityBarberId(barbersData[0].id);
      if (!blockBarberId) setBlockBarberId(barbersData[0].id);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  function getBarberName(id) {
    return barbers.find((barber) => barber.id === id)?.name || "Barber";
  }

  function formatTime(value) {
    if (!value) return "";
    return value.toString().slice(0, 5);
  }

  function isFullDay(block) {
    return (
      block.start_datetime?.endsWith("T00:00:00") &&
      block.end_datetime?.endsWith("T23:59:00")
    );
  }

  async function addAvailabilityRule() {
    await fetch(`${API_BASE}/api/availability-rules`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        barber_id: availabilityBarberId,
        weekday: WEEKDAY_MAP[availabilityDay],
        start_time: `${availabilityStart}:00`,
        end_time: `${availabilityEnd}:00`,
      }),
    });

    setMessage("Weekly availability added.");
    loadData();
  }

  async function deleteAvailabilityRule(id) {
    await fetch(`${API_BASE}/api/availability-rules/${id}`, {
      method: "DELETE",
    });

    setMessage("Weekly availability deleted.");
    loadData();
  }

  async function blockTime() {
    if (!blockBarberId || !blockStart || !blockEnd) return;

    await fetch(`${API_BASE}/api/blocked-times`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        barber_id: blockBarberId,
        reason: blockReason,
        start_datetime: blockStart,
        end_datetime: blockEnd,
      }),
    });

    setMessage("Time blocked.");
    setBlockStart("");
    setBlockEnd("");
    loadData();
  }

  async function blockFullDay(reason) {
    if (!blockBarberId || !fullDayDate) return;

    await fetch(`${API_BASE}/api/blocked-times`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        barber_id: blockBarberId,
        reason,
        start_datetime: `${fullDayDate}T00:00:00`,
        end_datetime: `${fullDayDate}T23:59:00`,
      }),
    });

    setMessage(`${reason} full day blocked.`);
    loadData();
  }

  async function deleteBlockedTime(id) {
    await fetch(`${API_BASE}/api/blocked-times/${id}`, {
      method: "DELETE",
    });

    setMessage("Blocked time removed.");
    loadData();
  }

  const sortedAvailabilityRules = useMemo(() => {
    return [...availabilityRules].sort((a, b) => {
      if (a.weekday !== b.weekday) return a.weekday - b.weekday;
      return a.start_time.localeCompare(b.start_time);
    });
  }, [availabilityRules]);

  const upcomingBlockedTimes = useMemo(() => {
    const now = new Date();

    return [...blockedTimes]
      .filter((block) => new Date(block.end_datetime) >= now)
      .sort(
        (a, b) =>
          new Date(a.start_datetime) - new Date(b.start_datetime)
      );
  }, [blockedTimes]);

  return (
    <main className="min-h-screen bg-gray-100 p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        <h1 className="text-4xl font-bold">Shop Setup</h1>

        {message && (
          <div className="bg-green-100 p-3 rounded-xl font-bold">
            {message}
          </div>
        )}

        <div className="bg-white p-6 rounded-2xl shadow space-y-4">
          <h2 className="text-2xl font-bold">Weekly Availability</h2>

          <select
            value={availabilityBarberId}
            onChange={(e) => setAvailabilityBarberId(e.target.value)}
            className="border p-3 rounded w-full"
          >
            {barbers.map((barber) => (
              <option key={barber.id} value={barber.id}>
                {barber.name}
              </option>
            ))}
          </select>

          <select
            value={availabilityDay}
            onChange={(e) => setAvailabilityDay(e.target.value)}
            className="border p-3 rounded w-full"
          >
            {Object.keys(WEEKDAY_MAP).map((day) => (
              <option key={day}>{day}</option>
            ))}
          </select>

          <input
            type="time"
            value={availabilityStart}
            onChange={(e) => setAvailabilityStart(e.target.value)}
            className="border p-3 rounded w-full"
          />

          <input
            type="time"
            value={availabilityEnd}
            onChange={(e) => setAvailabilityEnd(e.target.value)}
            className="border p-3 rounded w-full"
          />

          <button
            onClick={addAvailabilityRule}
            className="bg-black text-white px-4 py-3 rounded-xl"
          >
            Save Availability
          </button>

          {sortedAvailabilityRules.map((rule) => (
            <div
              key={rule.id}
              className="border rounded-xl p-3 flex justify-between"
            >
              <div>
                {WEEKDAY_NAMES[rule.weekday]} ·{" "}
                {formatTime(rule.start_time)} -{" "}
                {formatTime(rule.end_time)}
              </div>

              <button
                onClick={() => deleteAvailabilityRule(rule.id)}
                className="bg-red-500 text-white px-3 py-1 rounded"
              >
                Delete
              </button>
            </div>
          ))}
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

          {upcomingBlockedTimes.map((block) => (
            <div
              key={block.id}
              className="border rounded-xl p-3 flex justify-between"
            >
              <div>
                {block.reason} ·{" "}
                {isFullDay(block)
                  ? new Date(block.start_datetime).toLocaleDateString()
                  : new Date(block.start_datetime).toLocaleString()}
              </div>

              <button
                onClick={() => deleteBlockedTime(block.id)}
                className="bg-red-500 text-white px-3 py-1 rounded"
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}