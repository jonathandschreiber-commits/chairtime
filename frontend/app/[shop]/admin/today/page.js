"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

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

function localDateValue(date = new Date()) {
  const year = date.getFullYear();

  const month = String(
    date.getMonth() + 1
  ).padStart(2, "0");

  const day = String(
    date.getDate()
  ).padStart(2, "0");

  return `${year}-${month}-${day}`;
}

function datePart(value) {
  return String(value || "").slice(0, 10);
}

function timePart(value) {
  return String(value || "").slice(11, 16);
}

function displayShopName(slug) {
  return String(slug || "")
    .split("-")
    .filter(Boolean)
    .map(
      (word) =>
        word.charAt(0).toUpperCase() +
        word.slice(1)
    )
    .join(" ");
}

export default function AgendaPage() {
  const params = useParams();
  const router = useRouter();

  const shopSlug = params.shop;

  const [appointments, setAppointments] = useState([]);
  const [barbers, setBarbers] = useState([]);
  const [services, setServices] = useState([]);

  const [selectedDate, setSelectedDate] = useState(
    localDateValue()
  );

  const [selectedBarberId, setSelectedBarberId] =
    useState("");

  const [
    movingAppointmentId,
    setMovingAppointmentId,
  ] = useState("");

  const [moveDate, setMoveDate] = useState(
    localDateValue()
  );

  const [moveTime, setMoveTime] = useState("09:00");

  const [savingMove, setSavingMove] =
    useState(false);

  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        "/api/admin/agenda",
        {
          method: "GET",
          headers: {
            Accept: "application/json",
          },
          cache: "no-store",
        }
      );

      const data = await response.json();

      if (response.status === 401) {
        router.replace(
          `/login?next=${encodeURIComponent(
            `/${shopSlug}/admin/today`
          )}`
        );

        return;
      }

      if (!response.ok) {
        throw new Error(
          data?.error ||
            "The agenda could not be loaded."
        );
      }

      if (
        data.shop_slug &&
        data.shop_slug !== shopSlug
      ) {
        router.replace(
          `/${data.shop_slug}/admin/today`
        );

        return;
      }

      setAppointments(data.appointments || []);
      setBarbers(data.barbers || []);
      setServices(data.services || []);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "The agenda could not be loaded."
      );
    } finally {
      setLoading(false);
    }
  }, [router, shopSlug]);

  useEffect(() => {
    if (shopSlug) {
      loadData();
    }
  }, [loadData, shopSlug]);

  function sameDay(value, date) {
    return datePart(value) === date;
  }

  function formatTime(value) {
    return new Date(value).toLocaleTimeString(
      [],
      {
        hour: "numeric",
        minute: "2-digit",
      }
    );
  }

  function cleanPhone(phone) {
    return String(phone || "").replace(
      /\D/g,
      ""
    );
  }

  function barberName(id) {
    return (
      barbers.find(
        (barber) => barber.id === id
      )?.name || "Staff member"
    );
  }

  function serviceName(id) {
    return (
      services.find(
        (service) => service.id === id
      )?.name || "Service"
    );
  }

  function startMove(appointment) {
    setMovingAppointmentId(appointment.id);

    setMoveDate(
      datePart(appointment.start_datetime)
    );

    setMoveTime(
      timePart(appointment.start_datetime) ||
        "09:00"
    );

    setMessage("");
    setError("");
  }

  function cancelMove() {
    setMovingAppointmentId("");
    setSavingMove(false);
    setError("");
  }

  async function saveMove(appointmentId) {
    if (
      !moveDate ||
      !moveTime ||
      savingMove
    ) {
      return;
    }

    setSavingMove(true);
    setMessage("");
    setError("");

    const newStartDatetime =
      `${moveDate}T${moveTime}:00`;

    try {
      const response = await fetch(
        `/api/admin/appointments/${encodeURIComponent(
          appointmentId
        )}/reschedule`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify({
            new_start_datetime:
              newStartDatetime,
          }),
        }
      );

      const data = await response.json();

      if (response.status === 401) {
        router.replace("/login");
        return;
      }

      if (!response.ok) {
        throw new Error(
          data?.error ||
            "The appointment could not be moved."
        );
      }

      setMovingAppointmentId("");
      setSelectedDate(moveDate);
      setMessage("Appointment moved.");

      await loadData();
    } catch (moveError) {
      setError(
        moveError instanceof Error
          ? moveError.message
          : "The appointment could not be moved."
      );
    } finally {
      setSavingMove(false);
    }
  }

  async function updateStatus(
    appointmentId,
    appointmentStatus
  ) {
    setMessage("");
    setError("");

    try {
      const response = await fetch(
        `/api/admin/appointments/${encodeURIComponent(
          appointmentId
        )}/status`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify({
            status: appointmentStatus,
          }),
        }
      );

      const data = await response.json();

      if (response.status === 401) {
        router.replace("/login");
        return;
      }

      if (!response.ok) {
        throw new Error(
          data?.error ||
            "The appointment could not be updated."
        );
      }

      setMessage(
        `Marked ${
          STATUS_LABELS[appointmentStatus]
        }.`
      );

      await loadData();
    } catch (updateError) {
      setError(
        updateError instanceof Error
          ? updateError.message
          : "The appointment could not be updated."
      );
    }
  }

  const agendaAppointments = useMemo(() => {
    return appointments
      .filter((appointment) =>
        sameDay(
          appointment.start_datetime,
          selectedDate
        )
      )
      .filter((appointment) =>
        selectedBarberId
          ? appointment.barber_id ===
            selectedBarberId
          : true
      )
      .sort(
        (a, b) =>
          new Date(a.start_datetime) -
          new Date(b.start_datetime)
      );
  }, [
    appointments,
    selectedDate,
    selectedBarberId,
  ]);

  return (
    <main className="min-h-screen bg-orange-50 p-4 sm:p-8">
      <div className="max-w-4xl mx-auto space-y-6">
        <section className="rounded-3xl shadow-lg p-6 border border-orange-200 bg-gradient-to-r from-orange-100 via-amber-50 to-white">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-sm font-extrabold uppercase tracking-widest text-orange-700 mb-2">
                {displayShopName(shopSlug)}
              </p>

              <h1 className="text-5xl font-extrabold tracking-tight mb-2 text-gray-950">
                Daily Agenda
              </h1>

              <p className="text-lg text-gray-700">
                Today at a glance. Simple and fast.
              </p>
            </div>

            <Link
              href={`/${shopSlug}/admin`}
              className="inline-flex items-center justify-center rounded-xl bg-blue-600 px-5 py-3 font-bold text-white shadow hover:bg-blue-700"
            >
              Admin Home
            </Link>
          </div>

          {message ? (
            <p className="mt-4 rounded-xl bg-green-50 border border-green-200 px-4 py-3 font-bold text-green-700">
              {message}
            </p>
          ) : null}

          {error ? (
            <p className="mt-4 rounded-xl bg-red-50 border border-red-200 px-4 py-3 font-bold text-red-700">
              {error}
            </p>
          ) : null}
        </section>

        <section className="bg-white rounded-3xl shadow-lg p-6 border border-orange-200">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="block font-bold mb-2">
                Date
              </label>

              <input
                type="date"
                className="w-full border border-orange-200 rounded-xl p-4 text-lg bg-orange-50 focus:outline-none focus:ring-2 focus:ring-orange-300"
                value={selectedDate}
                onChange={(event) =>
                  setSelectedDate(
                    event.target.value
                  )
                }
              />
            </div>

            <div>
              <label className="block font-bold mb-2">
                Staff
              </label>

              <select
                className="w-full border border-orange-200 rounded-xl p-4 text-lg bg-orange-50 focus:outline-none focus:ring-2 focus:ring-orange-300"
                value={selectedBarberId}
                onChange={(event) =>
                  setSelectedBarberId(
                    event.target.value
                  )
                }
              >
                <option value="">
                  All staff
                </option>

                {barbers.map((barber) => (
                  <option
                    key={barber.id}
                    value={barber.id}
                  >
                    {barber.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          {loading ? (
            <div className="bg-white rounded-3xl shadow-lg p-6 border border-orange-200">
              <p className="text-2xl font-bold">
                Loading agenda...
              </p>
            </div>
          ) : null}

          {!loading &&
          agendaAppointments.length === 0 ? (
            <div className="bg-white rounded-3xl shadow-lg p-6 border border-orange-200">
              <p className="text-2xl font-bold">
                No appointments.
              </p>
            </div>
          ) : null}

          {!loading &&
            agendaAppointments.map(
              (appointment) => {
                const statusStyle =
                  STATUS_STYLES[
                    appointment.status
                  ] ||
                  STATUS_STYLES.confirmed;

                const statusLabel =
                  STATUS_LABELS[
                    appointment.status
                  ] || "Confirmed";

                const phone = cleanPhone(
                  appointment.customer_phone
                );

                const isMoving =
                  movingAppointmentId ===
                  appointment.id;

                return (
                  <div
                    key={appointment.id}
                    className={
                      "rounded-3xl shadow-lg p-6 border " +
                      statusStyle
                    }
                  >
                    <div className="flex justify-between gap-4">
                      <div>
                        <p className="text-4xl font-extrabold">
                          {formatTime(
                            appointment.start_datetime
                          )}
                        </p>

                        <p className="text-2xl font-bold mt-2">
                          {
                            appointment.customer_name
                          }
                        </p>

                        <p className="text-lg text-gray-900">
                          {serviceName(
                            appointment.service_id
                          )}{" "}
                          ·{" "}
                          {barberName(
                            appointment.barber_id
                          )}
                        </p>

                        <div className="grid grid-cols-2 gap-3 mt-4">
                          <a
                            className="bg-black text-white rounded-xl p-4 text-center font-bold"
                            href={`tel:${phone}`}
                          >
                            Call
                          </a>

                          <a
                            className="bg-gray-800 text-white rounded-xl p-4 text-center font-bold"
                            href={`sms:${phone}`}
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

                    {!isMoving ? (
                      <div className="grid grid-cols-2 sm:grid-cols-6 gap-3 mt-5">
                        <button
                          type="button"
                          onClick={() =>
                            updateStatus(
                              appointment.id,
                              "confirmed"
                            )
                          }
                          className="bg-blue-500 text-white rounded-xl p-4 font-bold"
                        >
                          Confirm
                        </button>

                        <button
                          type="button"
                          onClick={() =>
                            updateStatus(
                              appointment.id,
                              "completed"
                            )
                          }
                          className="bg-green-600 text-white rounded-xl p-4 font-bold"
                        >
                          Done
                        </button>

                        <button
                          type="button"
                          onClick={() =>
                            updateStatus(
                              appointment.id,
                              "no_show"
                            )
                          }
                          className="bg-yellow-500 text-white rounded-xl p-4 font-bold"
                        >
                          No-show
                        </button>

                        <button
                          type="button"
                          onClick={() =>
                            updateStatus(
                              appointment.id,
                              "canceled"
                            )
                          }
                          className="bg-red-500 text-white rounded-xl p-4 font-bold"
                        >
                          Cancel
                        </button>

                        <button
                          type="button"
                          onClick={() =>
                            startMove(appointment)
                          }
                          className="bg-gray-700 text-white rounded-xl p-4 font-bold"
                        >
                          Move
                        </button>

                        <Link
                          href={`/${shopSlug}/admin/customers?phone=${encodeURIComponent(
                            phone
                          )}`}
                          className="bg-purple-700 text-white rounded-xl p-4 font-bold text-center"
                        >
                          Customer
                        </Link>
                      </div>
                    ) : (
                      <div className="mt-5 rounded-2xl border bg-white p-4">
                        <p className="font-bold text-lg mb-3">
                          Move this appointment
                        </p>

                        <div className="grid gap-3 sm:grid-cols-3">
                          <div>
                            <label className="block font-bold mb-2">
                              New date
                            </label>

                            <input
                              type="date"
                              className="w-full border rounded-xl p-3"
                              value={moveDate}
                              onChange={(event) =>
                                setMoveDate(
                                  event.target.value
                                )
                              }
                            />
                          </div>

                          <div>
                            <label className="block font-bold mb-2">
                              New time
                            </label>

                            <input
                              type="time"
                              className="w-full border rounded-xl p-3"
                              value={moveTime}
                              onChange={(event) =>
                                setMoveTime(
                                  event.target.value
                                )
                              }
                            />
                          </div>

                          <button
                            type="button"
                            onClick={() =>
                              saveMove(
                                appointment.id
                              )
                            }
                            disabled={savingMove}
                            className="self-end bg-black text-white rounded-xl p-3 font-bold disabled:opacity-60"
                          >
                            {savingMove
                              ? "Moving..."
                              : "Save Move"}
                          </button>
                        </div>

                        <button
                          type="button"
                          onClick={cancelMove}
                          disabled={savingMove}
                          className="mt-3 bg-gray-400 text-white rounded-xl px-4 py-3 font-bold disabled:opacity-60"
                        >
                          Cancel Move
                        </button>
                      </div>
                    )}
                  </div>
                );
              }
            )}
        </section>
      </div>
    </main>
  );
}
