"use client";

import { useEffect, useMemo, useState } from "react";

const API_BASE = "https://chairtime-production-94da.up.railway.app";

export default function CustomersPage() {
const today = new Date().toISOString().slice(0, 10);

const [appointments, setAppointments] = useState([]);
const [barbers, setBarbers] = useState([]);
const [services, setServices] = useState([]);
const [search, setSearch] = useState("");
const [message, setMessage] = useState("");

const [rebookingCustomerKey, setRebookingCustomerKey] = useState("");
const [rebookDate, setRebookDate] = useState(today);
const [rebookTime, setRebookTime] = useState("");

async function loadData() {
const [appointmentsRes, barbersRes, servicesRes] = await Promise.all([
fetch(API_BASE + "/api/appointments"),
fetch(API_BASE + "/api/barbers"),
fetch(API_BASE + "/api/services"),
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

function servicePrice(id) {
return Number(services.find((service) => service.id === id)?.price || 0);
}

function formatDateTime(value) {
return new Date(value).toLocaleString([], {
month: "short",
day: "numeric",
hour: "numeric",
minute: "2-digit",
});
}

function inactivityTag(lastVisit) {
const now = new Date();
const last = new Date(lastVisit);
const diffDays = Math.floor(
(now - last) / (1000 * 60 * 60 * 24)
);


if (diffDays >= 90) {
  return {
    label: "Inactive 90+ days",
    style: "bg-red-600 text-white",
  };
}

if (diffDays >= 60) {
  return {
    label: "Inactive 60+ days",
    style: "bg-orange-500 text-white",
  };
}

if (diffDays >= 30) {
  return {
    label: "Inactive 30+ days",
    style: "bg-yellow-400 text-black",
  };
}

return null;


}

async function createRebookAppointment(latest) {
if (!rebookDate || !rebookTime) {
setMessage("Choose a date and time.");
return;
}


const payload = {
  barber_id: latest.barber_id,
  service_id: latest.service_id,
  customer_name: latest.customer_name,
  customer_phone: latest.customer_phone,
  start_datetime: rebookDate + "T" + rebookTime + ":00",
  notes: "Rebooked from customer history.",
};

const response = await fetch(API_BASE + "/api/appointments", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
  },
  body: JSON.stringify(payload),
});

if (response.ok) {
  setMessage("Customer rebooked.");
  setRebookingCustomerKey("");
  setRebookDate(today);
  setRebookTime("");
  loadData();
} else {
  const error = await response.json();
  setMessage(error.detail || "Could not rebook customer.");
}


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
  return new Date(b[0].start_datetime) - new Date(a[0].start_datetime);
});


}, [filteredAppointments]);

function customerStats(appointmentsGroup) {
const sorted = [...appointmentsGroup].sort(
(a, b) => new Date(b.start_datetime) - new Date(a.start_datetime)
);


const visits = sorted.length;
const lastVisit = sorted[0]?.start_datetime;

const barberCounts = {};

sorted.forEach((appointment) => {
  barberCounts[appointment.barber_id] =
    (barberCounts[appointment.barber_id] || 0) + 1;
});

const preferredBarberId = Object.keys(barberCounts).sort(
  (a, b) => barberCounts[b] - barberCounts[a]
)[0];

const noShows = sorted.filter(
  (appointment) => appointment.status === "no_show"
).length;

const lifetimeRevenue = sorted
  .filter((appointment) => appointment.status === "completed")
  .reduce((sum, appointment) => {
    return sum + servicePrice(appointment.service_id);
  }, 0);

return {
  visits,
  lastVisit,
  preferredBarberId,
  noShows,
  lifetimeRevenue,
};


}

return ( <main className="min-h-screen bg-gray-100 p-4 sm:p-8"> <div className="max-w-5xl mx-auto space-y-6"> <section className="bg-white rounded-3xl shadow-lg p-6 border border-gray-200"> <h1 className="text-5xl font-extrabold tracking-tight mb-2">
Customers </h1>


      <p className="text-gray-900">
        Search customer history, notes, and rebook repeat clients.
      </p>

      {message && (
        <p className="mt-4 font-bold text-green-700">{message}</p>
      )}

      <div className="mt-6">
        <input
          className="w-full border rounded-2xl p-5 text-xl"
          placeholder="Search name, phone, or notes"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </div>
    </section>

    <section className="space-y-5">
      {groupedCustomers.map((appointmentsGroup) => {
        const latest = appointmentsGroup[0];
        const stats = customerStats(appointmentsGroup);
        const customerKey = latest.customer_phone || latest.customer_name;
        const isRebooking = rebookingCustomerKey === customerKey;
        const inactive = inactivityTag(stats.lastVisit);

        return (
          <div
            key={customerKey}
            className="bg-white rounded-3xl shadow-lg p-6 border border-gray-200"
          >
            <div className="flex flex-col sm:flex-row sm:justify-between gap-4">
              <div>
                <div className="flex gap-3 items-center flex-wrap">
                  <p className="text-3xl font-extrabold">
                    {latest.customer_name}
                  </p>

                  {inactive && (
                    <span
                      className={"px-3 py-1 rounded-full text-sm font-bold " + inactive.style}
                    >
                      {inactive.label}
                    </span>
                  )}
                </div>

                <a
                  href={"tel:" + latest.customer_phone}
                  className="text-lg font-bold underline mt-2 inline-block"
                >
                  {latest.customer_phone}
                </a>
              </div>

              <div className="grid grid-cols-3 gap-3 sm:w-96">
                <a
                  href={"tel:" + latest.customer_phone}
                  className="bg-black text-white rounded-xl p-4 text-center font-bold"
                >
                  Call
                </a>

                <a
                  href={"sms:" + latest.customer_phone}
                  className="bg-gray-800 text-white rounded-xl p-4 text-center font-bold"
                >
                  Text
                </a>

                <button
                  onClick={() => {
                    setRebookingCustomerKey(customerKey);
                    setRebookDate(today);
                    setRebookTime("");
                  }}
                  className="bg-blue-700 text-white rounded-xl p-4 text-center font-bold"
                >
                  Rebook
                </button>
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mt-6">
              <div className="bg-gray-100 rounded-xl p-4">
                <p className="text-sm font-bold">Visits</p>
                <p className="text-2xl font-extrabold">{stats.visits}</p>
              </div>

              <div className="bg-gray-100 rounded-xl p-4">
                <p className="text-sm font-bold">Last Visit</p>
                <p className="font-bold">
                  {new Date(stats.lastVisit).toLocaleDateString()}
                </p>
              </div>

              <div className="bg-gray-100 rounded-xl p-4">
                <p className="text-sm font-bold">Preferred Barber</p>
                <p className="font-bold">
                  {barberName(stats.preferredBarberId)}
                </p>
              </div>

              <div className="bg-gray-100 rounded-xl p-4">
                <p className="text-sm font-bold">No-shows</p>
                <p className="text-2xl font-extrabold">{stats.noShows}</p>
              </div>

              <div className="bg-gray-100 rounded-xl p-4">
                <p className="text-sm font-bold">Lifetime Revenue</p>
                <p className="text-2xl font-extrabold">
                  ${stats.lifetimeRevenue}
                </p>
              </div>
            </div>
          </div>
        );
      })}
    </section>
  </div>
</main>


);
}
