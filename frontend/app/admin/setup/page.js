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
  const [services, setServices] = useState([]);
  const [blockedTimes, setBlockedTimes] = useState([]);
  const [availabilityRules, setAvailabilityRules] = useState([]);

  // Services
  const [serviceBarberId, setServiceBarberId] = useState("");
  const [serviceName, setServiceName] = useState("");
  const [serviceDuration, setServiceDuration] = useState("30");
  const [servicePrice, setServicePrice] = useState("");

  // Weekly availability
  const [availabilityBarberId, setAvailabilityBarberId] = useState("");
  const [availabilityDay, setAvailabilityDay] = useState("Monday");
  const [availabilityStart, setAvailabilityStart] = useState("09:00");
  const [availabilityEnd, setAvailabilityEnd] = useState("17:00");

  // Blocked time
  const [blockBarberId, setBlockBarberId] = useState("");
  const [blockReason, setBlockReason] = useState("Lunch");
  const [blockStart, setBlockStart] = useState("");
  const [blockEnd, setBlockEnd] = useState("");
  const [fullDayDate, setFullDayDate] = useState(
    new Date().toISOString().slice(0, 10)
  );

  const [message, setMessage] = useState("");

  async function loadData() {
    try {
      const [barbersRes, servicesRes, blockedRes, availabilityRes] =
        await Promise.all([
          fetch(`${API_BASE}/api/barbers`),
          fetch(`${API_BASE}/api/services`),
          fetch(`${API_BASE}/api/blocked-times`),
          fetch(`${API_BASE}/api/availability-rules`),
        ]);

      const barbersData = await barbersRes.json();
      const servicesData = await servicesRes.json();
      const blockedData = await blockedRes.json();
      const availabilityData = await availabilityRes.json();

      setBarbers(barbersData);
      setServices(servicesData);
      setBlockedTimes(blockedData);
      setAvailabilityRules(availabilityData);

      if (barbersData.length > 0) {
        setServiceBarberId((current) => current || barbersData[0].id);
        setAvailabilityBarberId(
          (current) => current || barbersData[0].id
        );
        setBlockBarberId((current) => current || barbersData[0].id);
      }
    } catch (error) {
      console.error(error);
      setMessage("Could not load shop setup.");
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

  async function addService() {
    if (!serviceBarberId || !serviceName.trim()) {
      setMessage("Choose a barber and enter a service name.");
      return;
    }

    const duration = Number(serviceDuration);
    const price = Number(servicePrice);

    if (!duration || duration <= 0) {
      setMessage("Enter a valid service duration.");
      return;
    }

    if (servicePrice === "" || Number.isNaN(price) || price < 0) {
      setMessage("Enter a valid service price.");
      return;
    }

    const response = await fetch(`${API_BASE}/api/services`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        barber_id: serviceBarberId,
        name: serviceName.trim(),
        duration_minutes: duration,
        price: price,
      }),
    });

    if (!response.ok) {
      setMessage("Could not add service.");
      return;
    }

    setMessage("Service added.");
    setServiceName("");
    setServiceDuration("30");
    setServicePrice("");
    loadData();
  }

  async function deleteService(id) {
    const response = await fetch(`${API_BASE}/api/services/${id}`, {
      method: "DELETE",
    });

    if (!response.ok) {
      setMessage("Could not delete service.");
      return;
    }

    setMessage("Service deleted.");
    loadData();
  }

  async function addAvailabilityRule() {
    if (!availabilityBarberId) return;

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

  const selectedBarberServices = useMemo(() => {
    return services
      .filter((service) => service.barber_id === serviceBarberId)
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [services, serviceBarberId]);

  const sortedAvailabilityRules = useMemo(() => {
    return [...availabilityRules]
      .filter((rule) => rule.barber_id === availabilityBarberId)
      .sort((a, b) => {
        if (a.weekday !== b.weekday) return a.weekday - b.weekday;
        return a.start_time.localeCompare(b.start_time);
      });
  }, [availabilityRules, availabilityBarberId]);

  const upcomingBlockedTimes = useMemo(() => {
    const now = new Date();

    return [...blockedTimes]
      .filter(
        (block) =>
          block.barber_id === blockBarberId &&
          new Date(block.end_datetime) >= now
      )
      .sort(
        (a, b) =>
          new Date(a.start_datetime) - new Date(b.start_datetime)
      );
  }, [blockedTimes, blockBarberId]);

  return (
    <main className="min-h-screen bg-gray-100 p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        <h1 className="text-4xl font-bold">Shop Setup</h1>

        {message && (
          <div className="bg-green-100 p-3 rounded-xl font-bold">
            {message}
          </div>
        )}

        {/* SERVICES */}
        <div className="bg-white p-6 rounded-2xl shadow space-y-4">
          <h2 className="text-2xl font-bold">Services</h2>

          <select
            value={serviceBarberId}
            onChange={(e) => setServiceBarberId(e.target.value)}
            className="border p-3 rounded w-full"
          >
            {barbers.map((barber) => (
              <option key={barber.id} value={barber.id}>
                {barber.name}
              </option>
            ))}
          </select>

          <input
            type="text"
            placeholder="Service name"
            value={serviceName}
            onChange={(e) => setServiceName(e.target.value)}
            className="border p-3 rounded w-full"
          />

          <input
            type="number"
            min="1"
            placeholder="Duration in minutes"
            value={serviceDuration}
            onChange={(e) => setServiceDuration(e.target.value)}
            className="border p-3 rounded w-full"
          />

          <input
            type="number"
            min="0"
            step="0.01"
            placeholder="Price"
            value={servicePrice}
            onChange={(e) => setServicePrice(e.target.value)}
            className="border p-3 rounded w-full"
          />

          <button
            onClick={addService}
            className="bg-black text-white px-4 py-3 rounded-xl"
          >
            Add Service
          </button>

          <div className="space-y-2">
            {selectedBarberServices.length === 0 ? (
              <div className="text-gray-500">
                No services for this barber yet.
              </div>
            ) : (
              selectedBarberServices.map((service) => (
                <div
                  key={service.id}
                  className="border rounded-xl p-3 flex justify-between items-center"
                >
                  <div>
                    <div className="font-bold">{service.name}</div>
                    <div className="text-sm text-gray-600">
                      {service.duration_minutes} minutes · $
                      {Number(service.price).toFixed(2)}
                    </div>
                  </div>

                  <button
                    onClick={() => deleteService(service.id)}
                    className="bg-red-500 text-white px-3 py-1 rounded"
                  >
                    Delete
                  </button>
                </div>
              ))
            )}
          </div>
        </div>

        {/* WEEKLY AVAILABILITY */}
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

        {/* QUICK BLOCK TIME */}
        <div className="bg-white p-6 rounded-2xl shadow space-y-4">
          <h2 className="text-2xl font-bold">Quick Block Time</h2>

          <select
            value={blockBarberId}
            onChange={(e) => setBlockBarberId(e.target.value)}
            className="border p-3 rounded w-full"
          >
            {barbers.map((barber) => (
              <option key={barber.id} value={barber.id}>
                {barber.name}
              </option>
            ))}
          </select>

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

        {/* FULL DAY BLOCK */}
        <div className="bg-white p-6 rounded-2xl shadow space-y-4">
          <h2 className="text-2xl font-bold">Full Day Block</h2>

          <select
            value={blockBarberId}
            onChange={(e) => setBlockBarberId(e.target.value)}
            className="border p-3 rounded w-full"
          >
            {barbers.map((barber) => (
              <option key={barber.id} value={barber.id}>
                {barber.name}
              </option>
            ))}
          </select>

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
