"use client";

import { useEffect, useMemo, useState } from "react";

const API_BASE = "https://chairtime-production-94da.up.railway.app";

export default function CustomersPage() {
  const [appointments, setAppointments] = useState([]);
  const [barbers, setBarbers] = useState([]);
  const [services, setServices] = useState([]);
  const [search, setSearch] = useState("");

  async function loadData() {
    const [appointmentsRes, barbersRes, servicesRes] = await Promise.all([
      fetch(`${API_BASE}/api/appointments`),
      fetch(`${API_BASE}/api/barbers`),
      fetch(`${API_BASE}/api/services`),
    ]);

    setAppointments(await appointmentsRes.json());
    setBarbers(await barbersRes.json());
    setServices(await servicesRes.json());
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

  function formatDateTime(value) {
    return new Date(value).toLocaleString([], {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  }

  const filteredAppointments = useMemo(() => {
    const term = search.trim().toLowerCase();

    if (!term) {
      return appointments;
    }

    return appointments.filter((appointment) => {
      return (
        appointment.customer_name?.toLowerCase().includes(term) ||
        appointment.customer_phone?.includes(term) ||
        appointment.notes?.toLowerCase().includes(term)
      );
    });
  }, [appointments, search]);

  const groupedCustomers = useMemo(() => {
    const groups = {};

    filteredAppointments.forEach((appointment) => {
      const key = appointment.customer_phone || appointment.customer_name;

      if (!groups[key]) {
        groups[key] = [];
      }

      groups[key].push(appointment);
    });

    return Object.values(groups).sort((a, b) => {
      return (
        new Date(b[0].start_datetime) -
        new Date(a[0].start_datetime)
      );
    });
  }, [filteredAppointments]);

  return (
    <main className="min-h-screen bg-gray-100 p-4 sm:p-8">
      <div className="max-w-5xl mx-auto space-y-6">
        <section className="bg-white rounded-3xl shadow-lg p-6 border border-gray-200">
          <h1 className="text-5xl font-extrabold tracking-tight mb-2">
            Customers
          </h1>

          <p className="text-gray-900">
            Search customer history and notes.
          </p>

          <div className="mt-6">
            <input
              className="w-full border rounded-2xl p-5 text-xl"
              placeholder="Search name, phone, or notes"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </section>

        <section className="space-y-5">
          {groupedCustomers.length === 0 && (
            <div className="bg-white rounded-3xl shadow-lg p-6 border border-gray-200">
              <p className="text-2xl font-bold">
                No matching customers.
              </p>
            </div>
          )}

          {groupedCustomers.map((appointmentsGroup) => {
            const latest = appointmentsGroup[0];

            return (
              <div
                key={latest.id}
                className="bg-white rounded-3xl shadow-lg p-6 border border-gray-200"
              >
                <div className="flex flex-col sm:flex-row sm:justify-between gap-4">
                  <div>
                    <p className="text-3xl font-extrabold">
                      {latest.customer_name}
                    </p>

                    <a
                      href={`tel:${latest.customer_phone}`}
                      className="text-lg font-bold underline mt-2 inline-block"
                    >
                      {latest.customer_phone}
                    </a>
                  </div>

                  <div className="grid grid-cols-2 gap-3 sm:w-72">
                    <a
                      href={`tel:${latest.customer_phone}`}
                      className="bg-black text-white rounded-xl p-4 text-center font-bold"
                    >
                      Call
                    </a>

                    <a
                      href={`sms:${latest.customer_phone}`}
                      className="bg-gray-800 text-white rounded-xl p-4 text-center font-bold"
                    >
                      Text
                    </a>
                  </div>
                </div>

                <div className="mt-6 space-y-3">
                  {appointmentsGroup
                    .sort(
                      (a, b) =>
                        new Date(b.start_datetime) -
                        new Date(a.start_datetime)
                    )
                    .map((appointment) => (
                      <div
                        key={appointment.id}
                        className="border rounded-2xl p-4 bg-gray-50"
                      >
                        <div className="flex flex-col sm:flex-row sm:justify-between gap-2">
                          <div>
                            <p className="font-bold text-lg">
                              {formatDateTime(appointment.start_datetime)}
                            </p>

                            <p className="text-gray-900">
                              {serviceName(appointment.service_id)} ·{" "}
                              {barberName(appointment.barber_id)}
                            </p>

                            <p className="text-gray-900 capitalize">
                              Status: {appointment.status}
                            </p>
                          </div>
                        </div>

                        {appointment.notes && (
                          <div className="mt-3 bg-white border rounded-xl p-3">
                            <p className="font-bold">Notes</p>

                            <p className="text-gray-900">
                              {appointment.notes}
                            </p>
                          </div>
                        )}
                      </div>
                    ))}
                </div>
              </div>
            );
          })}
        </section>
      </div>
    </main>
  );
}