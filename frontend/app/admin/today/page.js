"use client";

import { useEffect, useMemo, useState } from "react";

const API_BASE = "https://chairtime-production-94da.up.railway.app";

const STATUS_LABELS = {
confirmed: "Confirmed",
completed: "Done",
no_show: "No-show",
canceled: "Canceled",
};

const STATUS_STYLES = {
confirmed: "bg-blue-100 border-blue-300",
completed: "bg-green-100 border-green-300",
no_show: "bg-yellow-100 border-yellow-300",
canceled: "bg-red-100 border-red-300",
};

export default function AgendaPage() {
const today = new Date().toISOString().slice(0, 10);

const [appointments, setAppointments] = useState([]);
const [barbers, setBarbers] = useState([]);
const [services, setServices] = useState([]);
const [selectedDate, setSelectedDate] = useState(today);
const [selectedBarberId, setSelectedBarberId] = useState("");
const [message, setMessage] = useState("");

const [editingNotesId, setEditingNotesId] = useState("");
const [editingNotesValue, setEditingNotesValue] = useState("");

const [movingAppointmentId, setMovingAppointmentId] = useState("");
const [moveDate, setMoveDate] = useState(today);
const [moveTime, setMoveTime] = useState("");

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

function sameDay(value, date) {
return String(value || "").slice(0, 10) === date;
}

function formatTime(value) {
return new Date(value).toLocaleTimeString([], {
hour: "numeric",
minute: "2-digit",
});
}

function cleanPhone(phone) {
return String(phone || "").replace(/\D/g, "");
}

function barberName(id) {
return barbers.find((barber) => barber.id === id)?.name || "Barber";
}

function serviceName(id) {
return services.find((service) => service.id === id)?.name || "Service";
}

async function updateStatus(appointmentId, status) {
const response = await fetch(
API_BASE +
"/api/appointments/" +
appointmentId +
"/status?status=" +
status,
{ method: "PATCH" }
);


if (response.ok) {
  setMessage("Marked " + STATUS_LABELS[status] + ".");
  loadData();
} else {
  setMessage("Could not update appointment.");
}


}

function startMove(appointment) {
setMovingAppointmentId(appointment.id);
setMoveDate(String(appointment.start_datetime || "").slice(0, 10));
setMoveTime(String(appointment.start_datetime || "").slice(11, 16));
}

async function moveAppointment(appointmentId) {
if (!moveDate || !moveTime) {
setMessage("Choose a new date and time.");
return;
}


const newStart = moveDate + "T" + moveTime + ":00";

const response = await fetch(
  API_BASE +
    "/api/appointments/" +
    appointmentId +
    "/reschedule?new_start_datetime=" +
    encodeURIComponent(newStart),
  { method: "PATCH" }
);

if (response.ok) {
  setMessage("Appointment moved.");
  setMovingAppointmentId("");
  setMoveDate(today);
  setMoveTime("");
  loadData();
} else {
  const error = await response.json();
  setMessage(error.detail || "Could not move appointment.");
}


}

function startEditingNotes(appointment) {
setEditingNotesId(appointment.id);
setEditingNotesValue(appointment.notes || "");
}

async function saveNotes(appointmentId) {
const response = await fetch(
API_BASE +
"/api/appointments/" +
appointmentId +
"/notes?notes=" +
encodeURIComponent(editingNotesValue),
{ method: "PATCH" }
);


if (response.ok) {
  setMessage("Notes updated.");
  setEditingNotesId("");
  setEditingNotesValue("");
  loadData();
} else {
  setMessage("Could not update notes.");
}


}

function previousNotes(currentAppointment) {
const phone = cleanPhone(currentAppointment.customer_phone);


return appointments
  .filter(
    (appointment) => cleanPhone(appointment.customer_phone) === phone
  )
  .filter((appointment) => appointment.id !== currentAppointment.id)
  .filter(
    (appointment) =>
      appointment.notes && appointment.notes.trim() !== ""
  )
  .sort(
    (a, b) =>
      new Date(b.start_datetime) - new Date(a.start_datetime)
  )
  .slice(0, 3);


}

const agendaAppointments = useMemo(() => {
return appointments
.filter((appointment) =>
sameDay(appointment.start_datetime, selectedDate)
)
.filter((appointment) =>
selectedBarberId
? appointment.barber_id === selectedBarberId
: true
)
.sort(
(a, b) =>
new Date(a.start_datetime) - new Date(b.start_datetime)
);
}, [appointments, selectedDate, selectedBarberId]);

const todaySummary = useMemo(() => {
const completed = agendaAppointments.filter(
(appointment) => appointment.status === "completed"
).length;


const canceled = agendaAppointments.filter(
  (appointment) =>
    appointment.status === "canceled" ||
    appointment.status === "no_show"
).length;

const revenue = agendaAppointments
  .filter((appointment) => appointment.status === "completed")
  .reduce((sum, appointment) => {
    const service = services.find(
      (service) => service.id === appointment.service_id
    );

    return sum + Number(service?.price || 0);
  }, 0);

return {
  total: agendaAppointments.length,
  completed,
  canceled,
  revenue,
};


}, [agendaAppointments, services]);

return ( <main className="min-h-screen bg-gray-100 p-4 sm:p-8"> <div className="max-w-4xl mx-auto space-y-6"> <section className="bg-white rounded-3xl shadow-lg p-6 border border-gray-200"> <h1 className="text-5xl font-extrabold tracking-tight mb-2">
Daily Agenda </h1>


      <p className="text-gray-900">
        Today’s appointments. Simple and fast.
      </p>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-6">
        <div className="bg-gray-100 rounded-2xl p-4">
          <p className="text-sm font-bold">Appointments</p>
          <p className="text-3xl font-extrabold">{todaySummary.total}</p>
        </div>

        <div className="bg-gray-100 rounded-2xl p-4">
          <p className="text-sm font-bold">Completed</p>
          <p className="text-3xl font-extrabold">{todaySummary.completed}</p>
        </div>

        <div className="bg-gray-100 rounded-2xl p-4">
          <p className="text-sm font-bold">Canceled / No-show</p>
          <p className="text-3xl font-extrabold">{todaySummary.canceled}</p>
        </div>

        <div className="bg-gray-100 rounded-2xl p-4">
          <p className="text-sm font-bold">Revenue</p>
          <p className="text-3xl font-extrabold">${todaySummary.revenue}</p>
        </div>
      </div>

      {message && (
        <p className="mt-4 font-bold text-green-700">
          {message}
        </p>
      )}
    </section>

    <section className="bg-white rounded-3xl shadow-lg p-6 border border-gray-200">
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="block font-bold mb-2">Date</label>

          <input
            type="date"
            className="w-full border rounded-xl p-4 text-lg"
            value={selectedDate}
            onChange={(event) => setSelectedDate(event.target.value)}
          />
        </div>

        <div>
          <label className="block font-bold mb-2">Barber</label>

          <select
            className="w-full border rounded-xl p-4 text-lg"
            value={selectedBarberId}
            onChange={(event) => setSelectedBarberId(event.target.value)}
          >
            <option value="">All barbers</option>

            {barbers.map((barber) => (
              <option key={barber.id} value={barber.id}>
                {barber.name}
              </option>
            ))}
          </select>
        </div>
      </div>
    </section>

    <section className="space-y-4">
      {agendaAppointments.length === 0 && (
        <div className="bg-white rounded-3xl shadow-lg p-6 border border-gray-200">
          <p className="text-2xl font-bold">No appointments.</p>
        </div>
      )}

      {agendaAppointments.map((appointment) => {
        const statusStyle =
          STATUS_STYLES[appointment.status] || STATUS_STYLES.confirmed;

        const statusLabel =
          STATUS_LABELS[appointment.status] || "Confirmed";

        const phone = cleanPhone(appointment.customer_phone);
        const oldNotes = previousNotes(appointment);
        const isEditingCurrent = editingNotesId === appointment.id;
        const isMoving = movingAppointmentId === appointment.id;

        return (
          <div
            key={appointment.id}
            className={"rounded-3xl shadow-lg p-6 border " + statusStyle}
          >
            <div className="flex justify-between gap-4">
              <div>
                <p className="text-4xl font-extrabold">
                  {formatTime(appointment.start_datetime)}
                </p>

                <p className="text-2xl font-bold mt-2">
                  {appointment.customer_name}
                </p>

                <p className="text-lg text-gray-900">
                  {serviceName(appointment.service_id)} ·{" "}
                  {barberName(appointment.barber_id)}
                </p>

                <div className="grid grid-cols-2 gap-3 mt-4">
                  <a
                    className="bg-black text-white rounded-xl p-4 text-center font-bold"
                    href={"tel:" + phone}
                  >
                    Call
                  </a>

                  <a
                    className="bg-gray-800 text-white rounded-xl p-4 text-center font-bold"
                    href={"sms:" + phone}
                  >
                    Text
                  </a>
                </div>
              </div>

              <div>
                <span className="font-bold bg-white border rounded-full px-3 py-1">
                  {statusLabel}
                </span>
              </div>
            </div>

            {!isEditingCurrent && (
              <div className="mt-4">
                <div className="bg-white border rounded-2xl p-4">
                  <div className="flex justify-between items-center mb-2">
                    <p className="font-bold">Today’s Notes</p>

                    <button
                      onClick={() => startEditingNotes(appointment)}
                      className="text-sm font-bold underline"
                    >
                      Edit Notes
                    </button>
                  </div>

                  <p className="text-gray-900">
                    {appointment.notes || "No notes yet."}
                  </p>
                </div>
              </div>
            )}

            {isEditingCurrent && (
              <div className="mt-4 bg-white border rounded-2xl p-4">
                <p className="font-bold mb-3">Edit Today’s Notes</p>

                <textarea
                  className="w-full border rounded-xl p-4 min-h-32"
                  value={editingNotesValue}
                  onChange={(event) =>
                    setEditingNotesValue(event.target.value)
                  }
                />

                <div className="grid grid-cols-2 gap-3 mt-4">
                  <button
                    onClick={() => saveNotes(appointment.id)}
                    className="bg-black text-white rounded-xl p-4 font-bold"
                  >
                    Save Notes
                  </button>

                  <button
                    onClick={() => {
                      setEditingNotesId("");
                      setEditingNotesValue("");
                    }}
                    className="bg-gray-300 rounded-xl p-4 font-bold"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {oldNotes.length > 0 && (
              <div className="mt-4 bg-white border rounded-2xl p-4">
                <p className="font-bold mb-3">Previous Notes</p>

                <div className="space-y-3">
                  {oldNotes.map((oldAppointment) => {
                    const isEditingOld =
                      editingNotesId === oldAppointment.id;

                    return (
                      <div
                        key={oldAppointment.id}
                        className="border rounded-xl p-3 bg-gray-50"
                      >
                        <div className="flex justify-between gap-3">
                          <p className="font-bold text-sm">
                            {new Date(
                              oldAppointment.start_datetime
                            ).toLocaleDateString()}
                          </p>

                          {!isEditingOld && (
                            <button
                              onClick={() =>
                                startEditingNotes(oldAppointment)
                              }
                              className="text-sm font-bold underline"
                            >
                              Edit
                            </button>
                          )}
                        </div>

                        {!isEditingOld && (
                          <p className="text-gray-900 mt-1">
                            {oldAppointment.notes}
                          </p>
                        )}

                        {isEditingOld && (
                          <div className="mt-3">
                            <textarea
                              className="w-full border rounded-xl p-3 min-h-24 bg-white"
                              value={editingNotesValue}
                              onChange={(event) =>
                                setEditingNotesValue(event.target.value)
                              }
                            />

                            <div className="grid grid-cols-2 gap-3 mt-3">
                              <button
                                onClick={() =>
                                  saveNotes(oldAppointment.id)
                                }
                                className="bg-black text-white rounded-xl p-3 font-bold"
                              >
                                Save
                              </button>

                              <button
                                onClick={() => {
                                  setEditingNotesId("");
                                  setEditingNotesValue("");
                                }}
                                className="bg-gray-300 rounded-xl p-3 font-bold"
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {isMoving && (
              <div className="mt-4 bg-white border rounded-2xl p-4">
                <p className="font-bold mb-3">Move Appointment</p>

                <div className="grid gap-3 sm:grid-cols-2">
                  <input
                    type="date"
                    className="border rounded-xl p-4"
                    value={moveDate}
                    onChange={(event) => setMoveDate(event.target.value)}
                  />

                  <input
                    type="time"
                    className="border rounded-xl p-4"
                    value={moveTime}
                    onChange={(event) => setMoveTime(event.target.value)}
                  />
                </div>

                <div className="grid grid-cols-2 gap-3 mt-4">
                  <button
                    onClick={() => moveAppointment(appointment.id)}
                    className="bg-black text-white rounded-xl p-4 font-bold"
                  >
                    Save Move
                  </button>

                  <button
                    onClick={() => {
                      setMovingAppointmentId("");
                      setMoveDate(today);
                      setMoveTime("");
                    }}
                    className="bg-gray-300 rounded-xl p-4 font-bold"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mt-5">
              <button
                onClick={() => updateStatus(appointment.id, "confirmed")}
                className="bg-blue-500 text-white rounded-xl p-4 font-bold"
              >
                Confirm
              </button>

              <button
                onClick={() => updateStatus(appointment.id, "completed")}
                className="bg-green-600 text-white rounded-xl p-4 font-bold"
              >
                Done
              </button>

              <button
                onClick={() => updateStatus(appointment.id, "no_show")}
                className="bg-yellow-500 text-white rounded-xl p-4 font-bold"
              >
                No-show
              </button>

              <button
                onClick={() => updateStatus(appointment.id, "canceled")}
                className="bg-red-500 text-white rounded-xl p-4 font-bold"
              >
                Cancel
              </button>

              <button
                onClick={() => startMove(appointment)}
                className="bg-gray-700 text-white rounded-xl p-4 font-bold"
              >
                Move
              </button>
            </div>
          </div>
        );
      })}
    </section>
  </div>
</main>


);
}
