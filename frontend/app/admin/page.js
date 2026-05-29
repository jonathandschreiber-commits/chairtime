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

export default function AdminPage() {
  const [barbers, setBarbers] = useState([]);
  const [services, setServices] = useState([]);
  const [blockedTimes, setBlockedTimes] = useState([]);
  const [availabilityRules, setAvailabilityRules] = useState([]);

  const [newBarberName, setNewBarberName] = useState("");
  const [serviceName, setServiceName] = useState("");
  const [serviceDuration, setServiceDuration] = useState("");
  const [servicePrice, setServicePrice] = useState("");

  const [availabilityBarberId, setAvailabilityBarberId] = useState("");
  const [availabilityDay, setAvailabilityDay] = useState("Monday");
  const [availabilityStart, setAvailabilityStart] = useState("09:00");
  const [availabilityEnd, setAvailabilityEnd] = useState("17:00");

  const [blockBarberId, setBlockBarberId] = useState("");
  const [blockReason, setBlockReason] = useState("Lunch");
  const [blockStart, setBlockStart] = useState("");
  const [blockEnd, setBlockEnd] = useState("");

  const [message, setMessage] = useState("");

  async function loadData() {
    const [barbersRes, servicesRes, blockedRes, availabilityRes] =
      await Promise.all([
        fetch(`${API_BASE}/api/barbers`),
        fetch(`${API_BASE}/api/services`),
        fetch(`${API_BASE}/api/blocked-times`),
        fetch(`${API_BASE}/api/availability-rules`),
      ]);

    const barbersData = await barbersRes.json();

    setBarbers(barbersData);
    setServices(await servicesRes.json());
    setBlockedTimes(await blockedRes.json());
    setAvailabilityRules(await availabilityRes.json());

    if (barbersData.length > 0) {
      if (!availabilityBarberId) {
        setAvailabilityBarberId(barbersData[0].id);
      }

      if (!blockBarberId) {
        setBlockBarberId(barbersData[0].id);
      }
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

  async function addBarber() {
    if (!newBarberName) return;

    await fetch(`${API_BASE}/api/barbers`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        name: newBarberName,
        shop_name: "ChairTime Barbershop",
        phone: "",
        timezone: "America/New_York",
      }),
    });

    setNewBarberName("");
    setMessage("Barber added.");
    loadData();
  }

  async function addService() {
    if (!serviceName || !serviceDuration || !servicePrice) return;

    await fetch(`${API_BASE}/api/services`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        barber_id: barbers[0]?.id,
        name: serviceName,
        duration_minutes: Number(serviceDuration),
        price: Number(servicePrice),
      }),
    });

    setServiceName("");
    setServiceDuration("");
    setServicePrice("");

    setMessage("Service added.");
    loadData();
  }

  async function addAvailabilityRule() {
    await fetch(`${API_BASE}/api/availability-rules`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
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
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        barber_id: blockBarberId,
        reason: blockReason,
        start_datetime: blockStart,
        end_datetime: blockEnd,
      }),
    });

    setBlockReason("Lunch");
    setBlockStart("");
    setBlockEnd("");

    setMessage("Time blocked.");
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
      const barberCompare = getBarberName(a.barber_id).localeCompare(
        getBarberName(b.barber_id)
      );

      if (barberCompare !== 0) return barberCompare;

      if (a.weekday !== b.weekday) {
        return a.weekday - b.weekday;
      }

      return a.start_time.localeCompare(b.start_time);
    });
  }, [availabilityRules, barbers]);

  const sortedBlockedTimes = useMemo(() => {
    return [...blockedTimes].sort((a, b) => {
      const barberCompare = getBarberName(a.barber_id).localeCompare(
        getBarberName(b.barber_id)
      );

      if (barberCompare !== 0) return barberCompare;

      return new Date(a.start_datetime) - new Date(b.start_datetime);
    });
  }, [blockedTimes, barbers]);

  return (
    <main className="min-h-screen bg-gray-100 p-4 sm:p-10">
      <div className="max-w-6xl mx-auto space-y-8">

        <div className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-gray-200">
          <h1 className="text-5xl font-extrabold tracking-tight mb-3">
            ChairTime Admin
          </h1>

          <p className="text-gray-900">
            Manage barbers, services, schedules, and blocked time.
          </p>

          {message && (
            <p className="mt-4 font-semibold text-green-700">
              {message}
            </p>
          )}
        </div>

        <section className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-gray-200">
          <h2 className="text-3xl font-bold mb-6">
            Add Barber / Staff
          </h2>

          <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
            <input
              className="border rounded-xl p-3"
              placeholder="Barber name"
              value={newBarberName}
              onChange={(e) => setNewBarberName(e.target.value)}
            />

            <button
              onClick={addBarber}
              className="bg-black text-white rounded-xl px-6 py-3 font-semibold"
            >
              Add Barber
            </button>
          </div>
        </section>

        <section className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-gray-200">
          <h2 className="text-3xl font-bold mb-6">
            Add Service
          </h2>

          <div className="grid gap-3 sm:grid-cols-4">
            <input
              className="border rounded-xl p-3"
              placeholder="Service name"
              value={serviceName}
              onChange={(e) => setServiceName(e.target.value)}
            />

            <input
              className="border rounded-xl p-3"
              placeholder="Duration"
              value={serviceDuration}
              onChange={(e) => setServiceDuration(e.target.value)}
            />

            <input
              className="border rounded-xl p-3"
              placeholder="Price"
              value={servicePrice}
              onChange={(e) => setServicePrice(e.target.value)}
            />

            <button
              onClick={addService}
              className="bg-black text-white rounded-xl px-6 py-3 font-semibold"
            >
              Add Service
            </button>
          </div>
        </section>

        <section className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-gray-200">
          <h2 className="text-3xl font-bold mb-6">
            Weekly Availability
          </h2>

          <div className="grid gap-3">
            <select
              className="border rounded-xl p-3"
              value={availabilityBarberId}
              onChange={(e) => setAvailabilityBarberId(e.target.value)}
            >
              {barbers.map((barber) => (
                <option key={barber.id} value={barber.id}>
                  {barber.name}
                </option>
              ))}
            </select>

            <select
              className="border rounded-xl p-3"
              value={availabilityDay}
              onChange={(e) => setAvailabilityDay(e.target.value)}
            >
              <option>Monday</option>
              <option>Tuesday</option>
              <option>Wednesday</option>
              <option>Thursday</option>
              <option>Friday</option>
              <option>Saturday</option>
              <option>Sunday</option>
            </select>

            <input
              type="time"
              className="border rounded-xl p-3"
              value={availabilityStart}
              onChange={(e) => setAvailabilityStart(e.target.value)}
            />

            <input
              type="time"
              className="border rounded-xl p-3"
              value={availabilityEnd}
              onChange={(e) => setAvailabilityEnd(e.target.value)}
            />

            <button
              onClick={addAvailabilityRule}
              className="bg-black text-white rounded-xl px-6 py-3 font-semibold"
            >
              Add Weekly Availability
            </button>
          </div>

          <div className="grid gap-3 mt-6">
            {sortedAvailabilityRules.map((rule) => (
              <div
                key={rule.id}
                className="border rounded-xl p-4 flex justify-between items-center"
              >
                <div>
                  <p className="font-semibold">
                    {getBarberName(rule.barber_id)}
                  </p>

                  <p className="text-gray-900">
                    {WEEKDAY_NAMES[rule.weekday]} ·{" "}
                    {formatTime(rule.start_time)} –{" "}
                    {formatTime(rule.end_time)}
                  </p>
                </div>

                <button
                  onClick={() => deleteAvailabilityRule(rule.id)}
                  className="bg-red-400 hover:bg-red-500 text-white px-4 py-2 rounded-xl"
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
        </section>

        <section className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-gray-200">
          <h2 className="text-3xl font-bold mb-6">
            Quick Block Time
          </h2>

          <div className="grid gap-3">
            <select
              className="border rounded-xl p-3"
              value={blockBarberId}
              onChange={(e) => setBlockBarberId(e.target.value)}
            >
              {barbers.map((barber) => (
                <option key={barber.id} value={barber.id}>
                  {barber.name}
                </option>
              ))}
            </select>

            <select
              className="border rounded-xl p-3"
              value={blockReason}
              onChange={(e) => setBlockReason(e.target.value)}
            >
              <option>Lunch</option>
              <option>Break</option>
              <option>Vacation</option>
              <option>Personal</option>
              <option>Closed</option>
            </select>

            <input
              type="datetime-local"
              className="border rounded-xl p-3"
              value={blockStart}
              onChange={(e) => setBlockStart(e.target.value)}
            />

            <input
              type="datetime-local"
              className="border rounded-xl p-3"
              value={blockEnd}
              onChange={(e) => setBlockEnd(e.target.value)}
            />

            <button
              onClick={blockTime}
              className="bg-black text-white rounded-xl px-6 py-3 font-semibold"
            >
              Block Time
            </button>
          </div>

          <div className="grid gap-3 mt-6">
            {sortedBlockedTimes.map((block) => (
              <div
                key={block.id}
                className="border rounded-xl p-4 flex justify-between items-center"
              >
                <div>
                  <p className="font-semibold">
                    {getBarberName(block.barber_id)} · {block.reason}
                  </p>

                  <p className="text-gray-900">
                    {new Date(block.start_datetime).toLocaleString()}
                  </p>
                </div>

                <button
                  onClick={() => deleteBlockedTime(block.id)}
                  className="bg-red-400 hover:bg-red-500 text-white px-4 py-2 rounded-xl"
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
        </section>

      </div>
    </main>
  );
}