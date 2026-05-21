"use client";

import { useEffect, useState } from "react";

const API_BASE = "https://chairtime-production-94da.up.railway.app";

export default function AdminPage() {
  const [barbers, setBarbers] = useState([]);
  const [services, setServices] = useState([]);
  const [blockedTimes, setBlockedTimes] = useState([]);
  const [availabilityRules, setAvailabilityRules] = useState([]);

  const [barberName, setBarberName] = useState("");

  const [serviceName, setServiceName] = useState("");
  const [serviceDuration, setServiceDuration] = useState("");
  const [servicePrice, setServicePrice] = useState("");

  const [editingBarberId, setEditingBarberId] = useState(null);
  const [editingServiceId, setEditingServiceId] = useState(null);

  const [editedBarberName, setEditedBarberName] = useState("");

  const [editedServiceName, setEditedServiceName] = useState("");
  const [editedServiceDuration, setEditedServiceDuration] = useState("");
  const [editedServicePrice, setEditedServicePrice] = useState("");

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
    const [
      barbersRes,
      servicesRes,
      blockedRes,
      availabilityRes,
    ] = await Promise.all([
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
      if (!blockBarberId) {
        setBlockBarberId(barbersData[0].id);
      }

      if (!availabilityBarberId) {
        setAvailabilityBarberId(barbersData[0].id);
      }
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  async function addBarber() {
    await fetch(`${API_BASE}/api/barbers`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        name: barberName,
        shop_name: "ChairTime Barbershop",
        phone: "",
        timezone: "America/New_York",
      }),
    });

    setBarberName("");
    setMessage("Barber added.");
    loadData();
  }

  async function updateBarber(id) {
    await fetch(`${API_BASE}/api/barbers/${id}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        name: editedBarberName,
      }),
    });

    setEditingBarberId(null);
    setMessage("Barber updated.");
    loadData();
  }

  async function deleteBarber(id) {
    await fetch(`${API_BASE}/api/barbers/${id}`, {
      method: "DELETE",
    });

    setMessage("Barber deleted.");
    loadData();
  }

  async function addService() {
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

  async function updateService(id) {
    await fetch(`${API_BASE}/api/services/${id}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        name: editedServiceName,
        duration_minutes: Number(editedServiceDuration),
        price: Number(editedServicePrice),
      }),
    });

    setEditingServiceId(null);
    setMessage("Service updated.");
    loadData();
  }

  async function deleteService(id) {
    await fetch(`${API_BASE}/api/services/${id}`, {
      method: "DELETE",
    });

    setMessage("Service deleted.");
    loadData();
  }

  async function addAvailabilityRule() {
    const weekdayMap = {
      Sunday: 0,
      Monday: 1,
      Tuesday: 2,
      Wednesday: 3,
      Thursday: 4,
      Friday: 5,
      Saturday: 6,
    };

    await fetch(`${API_BASE}/api/availability-rules`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        barber_id: availabilityBarberId,
        weekday: weekdayMap[availabilityDay],
        start_time: `${availabilityStart}:00`,
        end_time: `${availabilityEnd}:00`,
      }),
    });

    setMessage("Availability rule added.");
    loadData();
  }

  async function deleteAvailabilityRule(id) {
    await fetch(`${API_BASE}/api/availability-rules/${id}`, {
      method: "DELETE",
    });

    setMessage("Availability rule deleted.");
    loadData();
  }

  async function blockTime() {
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

  return (
    <main className="min-h-screen bg-gray-100 p-4 sm:p-10">
      <div className="max-w-6xl mx-auto space-y-8">

        <div className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-gray-200">
          <h1 className="text-5xl font-extrabold tracking-tight mb-3">
            ChairTime Admin
          </h1>

          <p className="text-gray-900">
            Manage staff, services, schedules, and blocked time.
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
              value={barberName}
              onChange={(e) => setBarberName(e.target.value)}
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
            Barbers / Staff
          </h2>

          <div className="grid gap-3">
            {barbers.map((barber) => (
              <div
                key={barber.id}
                className="border rounded-xl p-4 flex justify-between items-center"
              >
                {editingBarberId === barber.id ? (
                  <div className="flex gap-2 w-full">
                    <input
                      className="border rounded-xl p-2 flex-1"
                      value={editedBarberName}
                      onChange={(e) =>
                        setEditedBarberName(e.target.value)
                      }
                    />

                    <button
                      onClick={() => updateBarber(barber.id)}
                      className="bg-green-600 text-white px-4 py-2 rounded-xl"
                    >
                      Save
                    </button>

                    <button
                      onClick={() => setEditingBarberId(null)}
                      className="bg-gray-400 text-white px-4 py-2 rounded-xl"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <>
                    <p className="font-semibold">
                      {barber.name}
                    </p>

                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          setEditingBarberId(barber.id);
                          setEditedBarberName(barber.name);
                        }}
                        className="bg-blue-400 hover:bg-blue-500 text-white px-4 py-2 rounded-xl"
                      >
                        Edit
                      </button>

                      <button
                        onClick={() => deleteBarber(barber.id)}
                        className="bg-red-400 hover:bg-red-500 text-white px-4 py-2 rounded-xl"
                      >
                        Delete
                      </button>
                    </div>
                  </>
                )}
              </div>
            ))}
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
            Services
          </h2>

          <div className="grid gap-3">
            {services.map((service) => (
              <div
                key={service.id}
                className="border rounded-xl p-4 flex justify-between items-center"
              >
                {editingServiceId === service.id ? (
                  <div className="flex gap-2 w-full">
                    <input
                      className="border rounded-xl p-2 flex-1"
                      value={editedServiceName}
                      onChange={(e) =>
                        setEditedServiceName(e.target.value)
                      }
                    />

                    <input
                      className="border rounded-xl p-2 w-24"
                      value={editedServiceDuration}
                      onChange={(e) =>
                        setEditedServiceDuration(e.target.value)
                      }
                    />

                    <input
                      className="border rounded-xl p-2 w-24"
                      value={editedServicePrice}
                      onChange={(e) =>
                        setEditedServicePrice(e.target.value)
                      }
                    />

                    <button
                      onClick={() => updateService(service.id)}
                      className="bg-green-600 text-white px-4 py-2 rounded-xl"
                    >
                      Save
                    </button>

                    <button
                      onClick={() => setEditingServiceId(null)}
                      className="bg-gray-400 text-white px-4 py-2 rounded-xl"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <>
                    <div>
                      <p className="font-semibold">
                        {service.name}
                      </p>

                      <p className="text-gray-900">
                        {service.duration_minutes} minutes
                      </p>
                    </div>

                    <div className="flex gap-2 items-center">
                      <p className="font-bold">
                        ${service.price}
                      </p>

                      <button
                        onClick={() => {
                          setEditingServiceId(service.id);
                          setEditedServiceName(service.name);
                          setEditedServiceDuration(
                            service.duration_minutes
                          );
                          setEditedServicePrice(service.price);
                        }}
                        className="bg-blue-400 hover:bg-blue-500 text-white px-4 py-2 rounded-xl"
                      >
                        Edit
                      </button>

                      <button
                        onClick={() => deleteService(service.id)}
                        className="bg-red-400 hover:bg-red-500 text-white px-4 py-2 rounded-xl"
                      >
                        Delete
                      </button>
                    </div>
                  </>
                )}
              </div>
            ))}
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
              onChange={(e) =>
                setAvailabilityBarberId(e.target.value)
              }
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
              onChange={(e) =>
                setAvailabilityDay(e.target.value)
              }
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
              onChange={(e) =>
                setAvailabilityStart(e.target.value)
              }
            />

            <input
              type="time"
              className="border rounded-xl p-3"
              value={availabilityEnd}
              onChange={(e) =>
                setAvailabilityEnd(e.target.value)
              }
            />

            <button
              onClick={addAvailabilityRule}
              className="bg-black text-white rounded-xl px-6 py-3 font-semibold"
            >
              Add Weekly Availability
            </button>
          </div>

          <div className="grid gap-3 mt-6">
            {availabilityRules.map((rule) => (
              <div
                key={rule.id}
                className="border rounded-xl p-4 flex justify-between items-center"
              >
                <div>
                  <p className="font-semibold">
                    {barbers.find(
                      (barber) => barber.id === rule.barber_id
                    )?.name || "Barber"}
                  </p>

                  <p className="text-gray-900">
                    Day {rule.weekday}: {rule.start_time} - {rule.end_time}
                  </p>
                </div>

                <button
                  onClick={() =>
                    deleteAvailabilityRule(rule.id)
                  }
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
            {blockedTimes.map((block) => (
              <div
                key={block.id}
                className="border rounded-xl p-4 flex justify-between items-center"
              >
                <div>
                  <p className="font-semibold">
                    {block.reason}
                  </p>

                  <p className="text-gray-900">
                    {new Date(
                      block.start_datetime
                    ).toLocaleString()}{" "}
                    →{" "}
                    {new Date(
                      block.end_datetime
                    ).toLocaleString()}
                  </p>
                </div>

                <button
                  onClick={() =>
                    deleteBlockedTime(block.id)
                  }
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