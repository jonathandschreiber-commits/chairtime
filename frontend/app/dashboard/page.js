"use client";

import { useEffect, useState } from "react";

export default function Dashboard() {
  const [appointments, setAppointments] = useState([]);

  function loadAppointments() {
    fetch("http://127.0.0.1:8000/api/appointments")
      .then((res) => res.json())
      .then((data) => setAppointments(data || []));
  }

  useEffect(() => {
    loadAppointments();
  }, []);

  async function cancelAppointment(id) {
    const response = await fetch(
      `http://127.0.0.1:8000/api/appointments/${id}/cancel`,
      { method: "PATCH" }
    );

    if (response.ok) {
      loadAppointments();
    }
  }

  return (
    <main className="min-h-screen bg-gray-100 p-10">
      <div className="max-w-4xl mx-auto bg-white rounded-2xl shadow p-8">
        <h1 className="text-4xl font-bold mb-2">ChairTime Dashboard</h1>

        <p className="text-gray-600 mb-8">View upcoming appointments</p>

        <button
          onClick={loadAppointments}
          className="mb-6 bg-black text-white px-4 py-2 rounded-lg"
        >
          Refresh
        </button>

        <div className="space-y-4">
          {appointments.length === 0 && (
            <p className="text-gray-500">No appointments yet.</p>
          )}

          {appointments.map((appointment) => (
            <div
              key={appointment.id}
              className="border rounded-xl p-4 flex justify-between items-center"
            >
              <div>
                <p className="font-semibold">{appointment.customer_name}</p>
                <p className="text-gray-600">{appointment.customer_phone}</p>
                <p className="text-gray-600">
                  {new Date(appointment.start_datetime).toLocaleString([], {
                    weekday: "short",
                    month: "short",
                    day: "numeric",
                    hour: "numeric",
                    minute: "2-digit",
                  })}
                </p>
              </div>

              <div className="flex gap-3 items-center">
                <span
                  className={`text-sm px-3 py-1 rounded-full ${
                    appointment.status === "cancelled"
                      ? "bg-red-100"
                      : "bg-green-100"
                  }`}
                >
                  {appointment.status}
                </span>

                {appointment.status !== "cancelled" && (
                  <button
                    onClick={() => cancelAppointment(appointment.id)}
                    className="bg-red-600 text-white px-4 py-2 rounded-lg"
                  >
                    Cancel
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}