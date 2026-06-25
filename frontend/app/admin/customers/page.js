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

const [editingCustomerKey, setEditingCustomerKey] = useState("");
const [editName, setEditName] = useState("");
const [editPhone, setEditPhone] = useState("");

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
const diffDays = Math.floor((now - last) / (1000 * 60 * 60 * 24));


if (diffDays >= 90) {
  return { label: "Inactive 90+ days", style: "bg-red-600 text-white" };
}

if (diffDays >= 60) {
  return { label: "Inactive 60+ days", style: "bg-orange-500 text-white" };
}

if (diffDays >= 30) {
  return { label: "Inactive 30+ days", style: "bg-yellow-400 text-black" };
}

return null;


}

async function updateCustomer(oldPhone) {
if (!editName || !editPhone) {
setMessage("Enter a name and phone number.");
return;
}


const response = await fetch(
  API_BASE +
    "/api/customers/update?old_phone=" +
    encodeURIComponent(oldPhone) +
    "&new_name=" +
    encodeURIComponent(editName) +
    "&new_phone=" +
    encodeURIComponent(editPhone),
  { method: "PATCH" }
);

if (response.ok) {
  setMessage("Customer updated.");
  setEditingCustomerKey("");
  setEditName("");
  setEditPhone("");
  loadData();
} else {
  const error = await response.json();
  setMessage(error.detail || "Could not update customer.");
}


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
      {groupedCustomers.length === 0 && (
        <div className="bg-white rounded-3xl shadow-lg p-6 border border-gray-200">
          <p className="text-2xl font-bold">No matching customers.</p>
        </div>
      )}

      {groupedCustomers.map((appointmentsGroup) => {
        const latest = appointmentsGroup[0];
        const stats = customerStats(appointmentsGroup);
        const customerKey = latest.customer_phone || latest.customer_name;
        const isRebooking = rebookingCustomerKey === customerKey;
        const isEditing = editingCustomerKey === customerKey;
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
                      className={
                        "px-3 py-1 rounded-full text-sm font-bold " +
                        inactive.style
                      }
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

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:w-[520px]">
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

                <button
                  onClick={() => {
                    setEditingCustomerKey(customerKey);
                    setEditName(latest.customer_name || "");
                    setEditPhone(latest.customer_phone || "");
                  }}
                  className="bg-green-700 text-white rounded-xl p-4 text-center font-bold"
                >
                  Edit
                </button>
              </div>
            </div>

            {isEditing && (
              <div className="mt-6 border rounded-2xl p-4 bg-green-50">
                <p className="font-bold text-xl mb-3">
                  Edit Customer
                </p>

                <div className="grid gap-3 sm:grid-cols-2">
                  <input
                    className="border rounded-xl p-4"
                    placeholder="Customer name"
                    value={editName}
                    onChange={(event) => setEditName(event.target.value)}
                  />

                  <input
                    className="border rounded-xl p-4"
                    placeholder="Customer phone"
                    value={editPhone}
                    onChange={(event) => setEditPhone(event.target.value)}
                  />
                </div>

                <div className="grid grid-cols-2 gap-3 mt-4">
                  <button
                    onClick={() => updateCustomer(latest.customer_phone)}
                    className="bg-black text-white rounded-xl p-4 font-bold"
                  >
                    Save Customer
                  </button>

                  <button
                    onClick={() => {
                      setEditingCustomerKey("");
                      setEditName("");
                      setEditPhone("");
                    }}
                    className="bg-gray-300 rounded-xl p-4 font-bold"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {isRebooking && (
              <div className="mt-6 border rounded-2xl p-4 bg-blue-50">
                <p className="font-bold text-xl mb-3">
                  Rebook {latest.customer_name}
                </p>

                <p className="text-gray-900 mb-3">
                  Same barber and service: {barberName(latest.barber_id)} ·{" "}
                  {serviceName(latest.service_id)}
                </p>

                <div className="grid gap-3 sm:grid-cols-2">
                  <input
                    type="date"
                    className="border rounded-xl p-4"
                    value={rebookDate}
                    onChange={(event) => setRebookDate(event.target.value)}
                  />

                  <input
                    type="time"
                    className="border rounded-xl p-4"
                    value={rebookTime}
                    onChange={(event) => setRebookTime(event.target.value)}
                  />
                </div>

                <div className="grid grid-cols-2 gap-3 mt-4">
                  <button
                    onClick={() => createRebookAppointment(latest)}
                    className="bg-black text-white rounded-xl p-4 font-bold"
                  >
                    Save Rebook
                  </button>

                  <button
                    onClick={() => {
                      setRebookingCustomerKey("");
                      setRebookDate(today);
                      setRebookTime("");
                    }}
                    className="bg-gray-300 rounded-xl p-4 font-bold"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

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
