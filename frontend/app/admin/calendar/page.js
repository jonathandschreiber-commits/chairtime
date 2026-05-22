"use client";

import { useEffect, useState } from "react";

const API_BASE = "https://chairtime-production-94da.up.railway.app";

export default function CalendarPage() {
  const [appointments, setAppointments] = useState([]);
  const [barbers, setBarbers] = useState([]);
  const [services, setServices] = useState([]);
  const [blockedTimes, setBlockedTimes] = useState([]);

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

  return (
    <main className="min-h-screen bg-gray-100 p-4 sm:p-10">
      <div className="max-w-6xl mx-auto space-y-8">
        <div className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-gray-200">
          <h1 className="text-5xl font-extrabold tracking-tight mb-3">
            ChairTime Calendar
          </h1>

          <p className="text-gray-900">
            View appointments and blocked time by barber.
          </p>
        </div>

        {barbers.map((barber) => (
          <section
            key={barber.id}
            className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-gray-200"
          >
            <h2 className="text-3xl font-bold mb-6">{barber.name}</h2>

            <div className="grid gap-4">
              {appointments
                .filter((appointment) => appointment.barber_id === barber.id)
                .map((appointment) => (
                  <div
                    key={appointment.id}
                    className="border rounded-xl p-4"
                  >
                    <p className="font-semibold">
                      {appointment.customer_name}
                    </p>

                    <p className="text-gray-900">
                      {serviceName(appointment.service_id)}
                    </p>

                    <p className="text-gray-900">
                      {new Date(
                        appointment.start_datetime
                      ).toLocaleString()}
                    </p>

                    <p className="text-gray-900">
                      Status: {appointment.status}
                    </p>
                  </div>
                ))}

              {blockedTimes
                .filter((block) => block.barber_id === barber.id)
                .map((block) => (
                  <div
                    key={block.id}
                    className="border rounded-xl p-4 bg-gray-100"
                  >
                    <p className="font-semibold">
                      Blocked: {block.reason}
                    </p>

                    <p className="text-gray-900">
                      {new Date(block.start_datetime).toLocaleString()} →{" "}
                      {new Date(block.end_datetime).toLocaleString()}
                    </p>
                  </div>
                ))}
            </div>
          </section>
        ))}
      </div>
    </main>
  );
}