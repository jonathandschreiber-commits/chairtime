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

    const barberIds =
      blockBarberId === "ALL"
        ? barbers.map((barber) => barber.id)
        : [blockBarberId];

    await Promise.all(
      barberIds.map((barberId) =>
        fetch(`${API_BASE}/api/blocked-times`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            barber_id: barberId,
            reason: blockReason,
            start_datetime: blockStart,
            end_datetime: blockEnd,
          }),
        })
      )
    );

    setMessage(
      blockBarberId === "ALL"
        ? "Time blocked for all staff."
        : "Time blocked."
    );

    setBlockStart("");
    setBlockEnd("");
    loadData();
  }

  async function blockFullDay(reason) {
    if (!blockBarberId || !fullDayDate) return;

    const barberIds =
      blockBarberId === "ALL"
        ? barbers.map((barber) => barber.id)
        : [blockBarberId];

    await Promise.all(
      barberIds.map((barberId) =>
        fetch(`${API_BASE}/api/blocked-times`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            barber_id: barberId,
            reason,
            start_datetime: `${fullDayDate}T00:00:00`,
            end_datetime: `${fullDayDate}T23:59:00`,
          }),
        })
      )
    );

    setMessage(
      blockBarberId === "ALL"
        ? `${reason} full day blocked for all staff.`
        : `${reason} full day blocked.`
    );

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
      if (a.weekday !== b.weekday) return a.weekday - b.weekday;

      return a.start_time.localeCompare(b.start_time);
    });
  }, [availabilityRules, barbers]);

  const upcomingBlockedTimes = useMemo(() => {
    const now = new Date();

    return [...blockedTimes]
      .filter((block) => new Date(block.end_datetime) >= now)
      .sort((a, b) => {
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
        <div className="bg-white rounded-3xl shadow-lg p-6 border border-gray-200">
          <h1 className="text-5xl font-extrabold mb-3">Shop Setup</h1>
          <p>Manage schedules and blocked time.</p>

          {message && (
            <p className="mt-4 font-semibold text-green-700">{message}</p>
          )}
        </div>
      </div>
    </main>
  );
}