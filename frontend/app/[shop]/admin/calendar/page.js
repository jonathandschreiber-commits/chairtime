"use client";

import { useParams, useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

const HOURS = [
  "08:00",
  "09:00",
  "10:00",
  "11:00",
  "12:00",
  "13:00",
  "14:00",
  "15:00",
  "16:00",
  "17:00",
  "18:00",
  "19:00",
];

const DAYS = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
];

const RECURRING_DAYS = [
  { label: "Mon", value: 0 },
  { label: "Tue", value: 1 },
  { label: "Wed", value: 2 },
  { label: "Thu", value: 3 },
  { label: "Fri", value: 4 },
  { label: "Sat", value: 5 },
  { label: "Sun", value: 6 },
];

const STATUS_STYLES = {
  confirmed: "bg-blue-100 border-blue-300",
  completed: "bg-green-100 border-green-300",
  no_show: "bg-yellow-100 border-yellow-300",
  canceled: "bg-red-100 border-red-300",
};

const STATUS_LABELS = {
  confirmed: "Confirmed",
  completed: "Completed",
  no_show: "No-show",
  canceled: "Canceled",
};

const BLOCK_REASON_OPTIONS = [
  "Lunch",
  "Meeting",
  "Personal",
  "Training",
  "Vacation",
  "Closed",
  "Sick",
  "Other",
];

function localDateValue(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(
    2,
    "0"
  );
  const day = String(date.getDate()).padStart(2, "0");

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

function defaultRecurringEndDate() {
  const date = new Date();
  date.setMonth(date.getMonth() + 3);

  return localDateValue(date);
}

export default function CalendarPage() {
  const params = useParams();
  const router = useRouter();

  const shopSlug = params.shop;

  const [appointments, setAppointments] = useState([]);
  const [barbers, setBarbers] = useState([]);
  const [services, setServices] = useState([]);
  const [blockedTimes, setBlockedTimes] = useState([]);

  const [selectedDate, setSelectedDate] = useState(
    localDateValue()
  );
  const [selectedBarberId, setSelectedBarberId] =
    useState("");
  const [viewMode, setViewMode] = useState("day");

  const [movingAppointmentId, setMovingAppointmentId] =
    useState("");
  const [moveDate, setMoveDate] = useState(
    localDateValue()
  );
  const [moveTime, setMoveTime] = useState("09:00");
  const [savingMove, setSavingMove] = useState(false);

  const [showBlockForm, setShowBlockForm] =
    useState(false);

  const [blockMode, setBlockMode] =
    useState("one-time");

  const [blockReason, setBlockReason] =
    useState("Lunch");
  const [customBlockReason, setCustomBlockReason] =
    useState("");

  const [blockDate, setBlockDate] = useState(
    localDateValue()
  );
  const [blockStartTime, setBlockStartTime] =
    useState("12:00");
  const [blockEndTime, setBlockEndTime] =
    useState("12:30");

  const [recurringStartDate, setRecurringStartDate] =
    useState(localDateValue());
  const [recurringEndDate, setRecurringEndDate] =
    useState(defaultRecurringEndDate());
  const [recurringDays, setRecurringDays] = useState([
    0,
    1,
    2,
    3,
    4,
  ]);

  const [savingBlock, setSavingBlock] =
    useState(false);
  const [deletingBlockId, setDeletingBlockId] =
    useState("");
  const [deletingSeriesId, setDeletingSeriesId] =
    useState("");

  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const [agendaResponse, blockedResponse] =
        await Promise.all([
          fetch("/api/admin/agenda", {
            method: "GET",
            headers: {
              Accept: "application/json",
            },
            cache: "no-store",
          }),
          fetch("/api/admin/blocked-times", {
            method: "GET",
            headers: {
              Accept: "application/json",
            },
            cache: "no-store",
          }),
        ]);

      if (
        agendaResponse.status === 401 ||
        blockedResponse.status === 401
      ) {
        router.replace(
          `/login?next=${encodeURIComponent(
            `/${shopSlug}/admin/calendar`
          )}`
        );

        return;
      }

      const agendaData = await agendaResponse.json();
      const blockedData = await blockedResponse.json();

      if (!agendaResponse.ok) {
        throw new Error(
          agendaData?.error ||
            "Calendar data could not be loaded."
        );
      }

      if (!blockedResponse.ok) {
        throw new Error(
          blockedData?.error ||
            "Blocked times could not be loaded."
        );
      }

      if (
        agendaData.shop_slug &&
        agendaData.shop_slug !== shopSlug
      ) {
        router.replace(
          `/${agendaData.shop_slug}/admin/calendar`
        );

        return;
      }

      const loadedBarbers = agendaData.barbers || [];

      setAppointments(
        agendaData.appointments || []
      );
      setBarbers(loadedBarbers);
      setServices(agendaData.services || []);
      setBlockedTimes(
        blockedData.blocked_times || []
      );

      setSelectedBarberId((currentValue) => {
        if (
          currentValue &&
          loadedBarbers.some(
            (barber) => barber.id === currentValue
          )
        ) {
          return currentValue;
        }

        return loadedBarbers[0]?.id || "";
      });
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Calendar data could not be loaded."
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
    return new Date(value).toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit",
    });
  }

  function serviceName(id) {
    return (
      services.find((service) => service.id === id)
        ?.name || "Service"
    );
  }

  function getWeekDates(dateString) {
    const date = new Date(`${dateString}T12:00:00`);
    const day = date.getDay();
    const sunday = new Date(date);

    sunday.setDate(date.getDate() - day);

    return Array.from({ length: 7 }, (_, index) => {
      const weekDate = new Date(sunday);

      weekDate.setDate(
        sunday.getDate() + index
      );

      return localDateValue(weekDate);
    });
  }

  function startMove(appointment) {
    setMovingAppointmentId(appointment.id);
    setMoveDate(datePart(appointment.start_datetime));
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

  async function updateAppointmentStatus(
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
            "Appointment status could not be updated."
        );
      }

      setMessage(
        `Appointment marked ${
          STATUS_LABELS[appointmentStatus]
        }.`
      );

      await loadData();
    } catch (statusError) {
      setError(
        statusError instanceof Error
          ? statusError.message
          : "Appointment status could not be updated."
      );
    }
  }

  function openBlockForm() {
    setBlockMode("one-time");
    setBlockDate(selectedDate);
    setRecurringStartDate(selectedDate);
    setRecurringEndDate(defaultRecurringEndDate());
    setBlockStartTime("12:00");
    setBlockEndTime("12:30");
    setBlockReason("Lunch");
    setCustomBlockReason("");
    setRecurringDays([0, 1, 2, 3, 4]);

    setShowBlockForm(true);
    setMessage("");
    setError("");
  }

  function closeBlockForm() {
    setShowBlockForm(false);
    setSavingBlock(false);
    setError("");
  }

  function toggleRecurringDay(dayValue) {
    setRecurringDays((currentDays) => {
      if (currentDays.includes(dayValue)) {
        return currentDays.filter(
          (day) => day !== dayValue
        );
      }

      return [
        ...currentDays,
        dayValue,
      ].sort((a, b) => a - b);
    });
  }

  function finalBlockReason() {
    return blockReason === "Other"
      ? customBlockReason.trim()
      : blockReason;
  }

  async function saveOneTimeBlockedTime() {
    const reason = finalBlockReason();

    if (!reason) {
      setError("Please enter a reason.");
      return false;
    }

    const startDatetime =
      `${blockDate}T${blockStartTime}:00`;

    const endDatetime =
      `${blockDate}T${blockEndTime}:00`;

    const response = await fetch(
      "/api/admin/blocked-times",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({
          barber_id: selectedBarberId,
          reason,
          start_datetime: startDatetime,
          end_datetime: endDatetime,
        }),
      }
    );

    const data = await response.json();

    if (response.status === 401) {
      router.replace("/login");
      return false;
    }

    if (!response.ok) {
      throw new Error(
        data?.error ||
          "Blocked time could not be created."
      );
    }

    setSelectedDate(blockDate);
    setMessage("Time blocked.");

    return true;
  }

  async function saveRecurringBlockedTime() {
    const reason = finalBlockReason();

    if (!reason) {
      setError("Please enter a reason.");
      return false;
    }

    if (recurringDays.length === 0) {
      setError(
        "Choose at least one day of the week."
      );
      return false;
    }

    const response = await fetch(
      "/api/admin/blocked-times/recurring",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({
          barber_id: selectedBarberId,
          reason,
          start_date: recurringStartDate,
          end_date: recurringEndDate,
          start_time: `${blockStartTime}:00`,
          end_time: `${blockEndTime}:00`,
          weekdays: recurringDays,
        }),
      }
    );

    const data = await response.json();

    if (response.status === 401) {
      router.replace("/login");
      return false;
    }

    if (!response.ok) {
      throw new Error(
        data?.error ||
          "Recurring blocked time could not be created."
      );
    }

    const created =
      data?.occurrences_created || 0;

    setSelectedDate(recurringStartDate);
    setMessage(
      `Recurring blocked time created (${created} occurrences).`
    );

    return true;
  }

  async function saveBlockedTime() {
    if (
      !selectedBarberId ||
      !blockStartTime ||
      !blockEndTime ||
      savingBlock
    ) {
      return;
    }

    setSavingBlock(true);
    setMessage("");
    setError("");

    try {
      let saved = false;

      if (blockMode === "recurring") {
        saved =
          await saveRecurringBlockedTime();
      } else {
        if (!blockDate) {
          setError("Please choose a date.");
          return;
        }

        saved =
          await saveOneTimeBlockedTime();
      }

      if (saved) {
        setShowBlockForm(false);
        await loadData();
      }
    } catch (blockError) {
      setError(
        blockError instanceof Error
          ? blockError.message
          : "Blocked time could not be created."
      );
    } finally {
      setSavingBlock(false);
    }
  }

  async function deleteBlockedTime(blockedTimeId) {
    if (deletingBlockId) {
      return;
    }

    const confirmed = window.confirm(
      "Delete this blocked time?"
    );

    if (!confirmed) {
      return;
    }

    setDeletingBlockId(blockedTimeId);
    setMessage("");
    setError("");

    try {
      const response = await fetch(
        `/api/admin/blocked-times/${encodeURIComponent(
          blockedTimeId
        )}`,
        {
          method: "DELETE",
          headers: {
            Accept: "application/json",
          },
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
            "Blocked time could not be deleted."
        );
      }

      setMessage("Blocked time deleted.");

      await loadData();
    } catch (deleteError) {
      setError(
        deleteError instanceof Error
          ? deleteError.message
          : "Blocked time could not be deleted."
      );
    } finally {
      setDeletingBlockId("");
    }
  }

  async function deleteBlockedTimeSeries(seriesId) {
    if (!seriesId || deletingSeriesId) {
      return;
    }

    const confirmed = window.confirm(
      "Delete every remaining blocked time in this recurring series?"
    );

    if (!confirmed) {
      return;
    }

    setDeletingSeriesId(seriesId);
    setMessage("");
    setError("");

    try {
      const response = await fetch(
        `/api/admin/blocked-time-series/${encodeURIComponent(
          seriesId
        )}`,
        {
          method: "DELETE",
          headers: {
            Accept: "application/json",
          },
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
            "Recurring series could not be deleted."
        );
      }

      setMessage(
        `Recurring series deleted (${data?.occurrences_deleted || 0} occurrences).`
      );

      await loadData();
    } catch (deleteError) {
      setError(
        deleteError instanceof Error
          ? deleteError.message
          : "Recurring series could not be deleted."
      );
    } finally {
      setDeletingSeriesId("");
    }
  }

  const selectedBarber = barbers.find(
    (barber) => barber.id === selectedBarberId
  );

  const dayAppointments = useMemo(() => {
    return appointments
      .filter(
        (appointment) =>
          appointment.barber_id ===
          selectedBarberId
      )
      .filter((appointment) =>
        sameDay(
          appointment.start_datetime,
          selectedDate
        )
      )
      .sort(
        (a, b) =>
          new Date(a.start_datetime) -
          new Date(b.start_datetime)
      );
  }, [
    appointments,
    selectedBarberId,
    selectedDate,
  ]);

  const dayBlockedTimes = useMemo(() => {
    return blockedTimes
      .filter(
        (block) =>
          block.barber_id === selectedBarberId
      )
      .filter((block) =>
        sameDay(
          block.start_datetime,
          selectedDate
        )
      )
      .sort(
        (a, b) =>
          new Date(a.start_datetime) -
          new Date(b.start_datetime)
      );
  }, [
    blockedTimes,
    selectedBarberId,
    selectedDate,
  ]);

  const weekDates = useMemo(
    () => getWeekDates(selectedDate),
    [selectedDate]
  );

  function appointmentItemsForHour(hourText) {
    const hour = Number(hourText.split(":")[0]);

    return dayAppointments.filter(
      (appointment) =>
        new Date(
          appointment.start_datetime
        ).getHours() === hour
    );
  }

  function blockedItemsForHour(hourText) {
    const hour = Number(hourText.split(":")[0]);

    return dayBlockedTimes.filter(
      (block) =>
        new Date(
          block.start_datetime
        ).getHours() === hour
    );
  }

  function weekItemsForDate(date) {
    const appointmentItems = appointments
      .filter(
        (appointment) =>
          appointment.barber_id ===
          selectedBarberId
      )
      .filter((appointment) =>
        sameDay(appointment.start_datetime, date)
      )
      .map((appointment) => ({
        type: "appointment",
        id: appointment.id,
        time: appointment.start_datetime,
        data: appointment,
      }));

    const blockedItems = blockedTimes
      .filter(
        (block) =>
          block.barber_id === selectedBarberId
      )
      .filter((block) =>
        sameDay(block.start_datetime, date)
      )
      .map((block) => ({
        type: "blocked",
        id: block.id,
        time: block.start_datetime,
        data: block,
      }));

    return [
      ...appointmentItems,
      ...blockedItems,
    ].sort(
      (a, b) =>
        new Date(a.time) - new Date(b.time)
    );
  }

  function appointmentCard(appointment) {
    const isMoving =
      movingAppointmentId === appointment.id;

    const statusStyle =
      STATUS_STYLES[appointment.status] ||
      STATUS_STYLES.confirmed;

    const statusLabel =
      STATUS_LABELS[appointment.status] ||
      "Confirmed";

    return (
      <div
        key={appointment.id}
        className={`rounded-xl p-4 border ${statusStyle}`}
      >
        <div className="flex justify-between gap-3 items-start">
          <div>
            <p className="font-bold text-lg">
              {formatTime(
                appointment.start_datetime
              )}{" "}
              ·{" "}
              <button
                type="button"
                onClick={() =>
                  router.push(
                    `/${shopSlug}/admin/customers?phone=${encodeURIComponent(
                      appointment.customer_phone
                    )}`
                  )
                }
                className="font-bold text-blue-700 underline hover:text-blue-900"
              >
                {appointment.customer_name}
              </button>
            </p>

            <p className="text-gray-900">
              {serviceName(
                appointment.service_id
              )}
            </p>

            <p className="text-gray-900">
              {appointment.customer_phone}
            </p>

            {appointment.notes ? (
              <div className="mt-3 rounded-xl bg-white border p-3 text-gray-900">
                <p className="font-bold">Notes</p>
                <p>{appointment.notes}</p>
              </div>
            ) : null}
          </div>

          <span className="font-bold text-sm bg-white border rounded-full px-3 py-1">
            {statusLabel}
          </span>
        </div>

        {!isMoving ? (
          <div className="flex flex-wrap gap-2 mt-4">
            <button
              type="button"
              onClick={() => startMove(appointment)}
              className="bg-purple-600 text-white px-3 py-2 rounded-xl text-sm font-semibold"
            >
              Move
            </button>

            <button
              type="button"
              onClick={() =>
                updateAppointmentStatus(
                  appointment.id,
                  "confirmed"
                )
              }
              className="bg-blue-500 text-white px-3 py-2 rounded-xl text-sm font-semibold"
            >
              Confirm
            </button>

            <button
              type="button"
              onClick={() =>
                updateAppointmentStatus(
                  appointment.id,
                  "completed"
                )
              }
              className="bg-green-600 text-white px-3 py-2 rounded-xl text-sm font-semibold"
            >
              Complete
            </button>

            <button
              type="button"
              onClick={() =>
                updateAppointmentStatus(
                  appointment.id,
                  "no_show"
                )
              }
              className="bg-yellow-500 text-white px-3 py-2 rounded-xl text-sm font-semibold"
            >
              No-show
            </button>

            <button
              type="button"
              onClick={() =>
                updateAppointmentStatus(
                  appointment.id,
                  "canceled"
                )
              }
              className="bg-red-500 text-white px-3 py-2 rounded-xl text-sm font-semibold"
            >
              Cancel
            </button>
          </div>
        ) : (
          <div className="mt-4 bg-white rounded-xl border p-4">
            <p className="font-bold mb-3">
              Move this appointment
            </p>

            <div className="grid gap-3 sm:grid-cols-3">
              <input
                type="date"
                className="border rounded-xl p-3"
                value={moveDate}
                onChange={(event) =>
                  setMoveDate(event.target.value)
                }
              />

              <input
                type="time"
                className="border rounded-xl p-3"
                value={moveTime}
                onChange={(event) =>
                  setMoveTime(event.target.value)
                }
              />

              <button
                type="button"
                onClick={() =>
                  saveMove(appointment.id)
                }
                disabled={savingMove}
                className="bg-black text-white rounded-xl px-4 py-3 font-semibold disabled:opacity-60"
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
              className="mt-3 bg-gray-400 text-white px-4 py-2 rounded-xl font-semibold disabled:opacity-60"
            >
              Cancel Move
            </button>
          </div>
        )}
      </div>
    );
  }

  function blockedTimeCard(block) {
    const recurring = Boolean(block.series_id);

    return (
      <div
        key={block.id}
        className="rounded-xl p-4 bg-gray-200 border border-gray-400"
      >
        <div className="flex flex-col gap-4 sm:flex-row sm:justify-between sm:items-start">
          <div>
            <p className="font-bold">
              {formatTime(block.start_datetime)} –{" "}
              {formatTime(block.end_datetime)}
            </p>

            <p className="text-gray-900">
              Blocked: {block.reason}
            </p>

            {recurring ? (
              <p className="text-sm font-semibold mt-1">
                Repeats weekly
              </p>
            ) : null}
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() =>
                deleteBlockedTime(block.id)
              }
              disabled={
                deletingBlockId === block.id
              }
              className="bg-red-500 text-white px-3 py-2 rounded-xl text-sm font-semibold disabled:opacity-60"
            >
              {deletingBlockId === block.id
                ? "Deleting..."
                : recurring
                  ? "Delete This"
                  : "Delete"}
            </button>

            {recurring ? (
              <button
                type="button"
                onClick={() =>
                  deleteBlockedTimeSeries(
                    block.series_id
                  )
                }
                disabled={
                  deletingSeriesId ===
                  block.series_id
                }
                className="bg-black text-white px-3 py-2 rounded-xl text-sm font-semibold disabled:opacity-60"
              >
                {deletingSeriesId ===
                block.series_id
                  ? "Deleting..."
                  : "Delete Series"}
              </button>
            ) : null}
          </div>
        </div>
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-gray-100 p-4 sm:p-10">
      <div className="max-w-7xl mx-auto space-y-8">
        <section className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-gray-200">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h1 className="text-5xl font-extrabold tracking-tight mb-3">
                {displayShopName(shopSlug)} Calendar
              </h1>

              <p className="text-gray-900">
                View appointments and manage blocked
                time.
              </p>
            </div>

            <button
              type="button"
              onClick={openBlockForm}
              disabled={!selectedBarberId}
              className="bg-black text-white rounded-xl px-5 py-3 font-bold disabled:opacity-50"
            >
              + Block Time
            </button>
          </div>

          {message ? (
            <p className="mt-4 font-semibold text-green-700">
              {message}
            </p>
          ) : null}

          {error ? (
            <p className="mt-4 font-semibold text-red-700">
              {error}
            </p>
          ) : null}
        </section>

        {showBlockForm ? (
          <section className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-gray-200">
            <h2 className="text-3xl font-bold mb-6">
              Block Time
            </h2>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="block font-semibold mb-2">
                  Staff
                </label>

                <select
                  className="w-full border rounded-xl p-3"
                  value={selectedBarberId}
                  onChange={(event) =>
                    setSelectedBarberId(
                      event.target.value
                    )
                  }
                >
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

              <div>
                <label className="block font-semibold mb-2">
                  Reason
                </label>

                <select
                  className="w-full border rounded-xl p-3"
                  value={blockReason}
                  onChange={(event) =>
                    setBlockReason(
                      event.target.value
                    )
                  }
                >
                  {BLOCK_REASON_OPTIONS.map(
                    (reason) => (
                      <option
                        key={reason}
                        value={reason}
                      >
                        {reason}
                      </option>
                    )
                  )}
                </select>
              </div>

              {blockReason === "Other" ? (
                <div className="sm:col-span-2">
                  <label className="block font-semibold mb-2">
                    Custom reason
                  </label>

                  <input
                    className="w-full border rounded-xl p-3"
                    value={customBlockReason}
                    onChange={(event) =>
                      setCustomBlockReason(
                        event.target.value
                      )
                    }
                    placeholder="Enter reason"
                  />
                </div>
              ) : null}
            </div>

            <div className="mt-6">
              <label className="block font-semibold mb-3">
                Repeat
              </label>

              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() =>
                    setBlockMode("one-time")
                  }
                  className={`px-4 py-3 rounded-xl font-bold border ${
                    blockMode === "one-time"
                      ? "bg-black text-white"
                      : "bg-white text-black"
                  }`}
                >
                  One-time
                </button>

                <button
                  type="button"
                  onClick={() =>
                    setBlockMode("recurring")
                  }
                  className={`px-4 py-3 rounded-xl font-bold border ${
                    blockMode === "recurring"
                      ? "bg-black text-white"
                      : "bg-white text-black"
                  }`}
                >
                  Repeat Weekly
                </button>
              </div>
            </div>

            {blockMode === "one-time" ? (
              <div className="grid gap-4 sm:grid-cols-2 mt-6">
                <div>
                  <label className="block font-semibold mb-2">
                    Date
                  </label>

                  <input
                    type="date"
                    className="w-full border rounded-xl p-3"
                    value={blockDate}
                    onChange={(event) =>
                      setBlockDate(event.target.value)
                    }
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block font-semibold mb-2">
                      Start
                    </label>

                    <input
                      type="time"
                      className="w-full border rounded-xl p-3"
                      value={blockStartTime}
                      onChange={(event) =>
                        setBlockStartTime(
                          event.target.value
                        )
                      }
                    />
                  </div>

                  <div>
                    <label className="block font-semibold mb-2">
                      End
                    </label>

                    <input
                      type="time"
                      className="w-full border rounded-xl p-3"
                      value={blockEndTime}
                      onChange={(event) =>
                        setBlockEndTime(
                          event.target.value
                        )
                      }
                    />
                  </div>
                </div>
              </div>
            ) : (
              <div className="space-y-5 mt-6">
                <div>
                  <label className="block font-semibold mb-3">
                    Days
                  </label>

                  <div className="flex flex-wrap gap-2">
                    {RECURRING_DAYS.map((day) => {
                      const selected =
                        recurringDays.includes(
                          day.value
                        );

                      return (
                        <button
                          key={day.value}
                          type="button"
                          onClick={() =>
                            toggleRecurringDay(
                              day.value
                            )
                          }
                          className={`px-4 py-3 rounded-xl font-bold border ${
                            selected
                              ? "bg-black text-white"
                              : "bg-white text-black"
                          }`}
                        >
                          {day.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="block font-semibold mb-2">
                      Starting
                    </label>

                    <input
                      type="date"
                      className="w-full border rounded-xl p-3"
                      value={recurringStartDate}
                      onChange={(event) =>
                        setRecurringStartDate(
                          event.target.value
                        )
                      }
                    />
                  </div>

                  <div>
                    <label className="block font-semibold mb-2">
                      Until
                    </label>

                    <input
                      type="date"
                      className="w-full border rounded-xl p-3"
                      value={recurringEndDate}
                      onChange={(event) =>
                        setRecurringEndDate(
                          event.target.value
                        )
                      }
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block font-semibold mb-2">
                      Start
                    </label>

                    <input
                      type="time"
                      className="w-full border rounded-xl p-3"
                      value={blockStartTime}
                      onChange={(event) =>
                        setBlockStartTime(
                          event.target.value
                        )
                      }
                    />
                  </div>

                  <div>
                    <label className="block font-semibold mb-2">
                      End
                    </label>

                    <input
                      type="time"
                      className="w-full border rounded-xl p-3"
                      value={blockEndTime}
                      onChange={(event) =>
                        setBlockEndTime(
                          event.target.value
                        )
                      }
                    />
                  </div>
                </div>
              </div>
            )}

            <div className="flex flex-wrap gap-3 mt-6">
              <button
                type="button"
                onClick={saveBlockedTime}
                disabled={savingBlock}
                className="bg-black text-white rounded-xl px-5 py-3 font-bold disabled:opacity-60"
              >
                {savingBlock
                  ? "Saving..."
                  : blockMode === "recurring"
                    ? "Save Recurring Block"
                    : "Save Blocked Time"}
              </button>

              <button
                type="button"
                onClick={closeBlockForm}
                disabled={savingBlock}
                className="bg-gray-400 text-white rounded-xl px-5 py-3 font-bold disabled:opacity-60"
              >
                Cancel
              </button>
            </div>
          </section>
        ) : null}

        <section className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-gray-200">
          <h2 className="text-3xl font-bold mb-6">
            Filters
          </h2>

          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <label className="block font-semibold mb-2">
                View
              </label>

              <select
                className="w-full border rounded-xl p-3"
                value={viewMode}
                onChange={(event) =>
                  setViewMode(event.target.value)
                }
              >
                <option value="day">Day</option>
                <option value="week">Week</option>
              </select>
            </div>

            <div>
              <label className="block font-semibold mb-2">
                Date
              </label>

              <input
                type="date"
                className="w-full border rounded-xl p-3"
                value={selectedDate}
                onChange={(event) =>
                  setSelectedDate(
                    event.target.value
                  )
                }
              />
            </div>

            <div>
              <label className="block font-semibold mb-2">
                Staff
              </label>

              <select
                className="w-full border rounded-xl p-3"
                value={selectedBarberId}
                onChange={(event) =>
                  setSelectedBarberId(
                    event.target.value
                  )
                }
              >
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

        {loading ? (
          <section className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-gray-200">
            <p className="text-2xl font-bold">
              Loading calendar...
            </p>
          </section>
        ) : null}

        {!loading && viewMode === "day" ? (
          <section className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-gray-200">
            <h2 className="text-3xl font-bold mb-6">
              Day View —{" "}
              {selectedBarber?.name || "Staff"} —{" "}
              {selectedDate}
            </h2>

            <div className="grid gap-3">
              {HOURS.map((hour) => {
                const appointmentsForHour =
                  appointmentItemsForHour(hour);

                const blockedForHour =
                  blockedItemsForHour(hour);

                return (
                  <div
                    key={hour}
                    className="border rounded-xl p-4"
                  >
                    <p className="font-bold mb-3">
                      {hour}
                    </p>

                    {appointmentsForHour.length ===
                      0 &&
                    blockedForHour.length === 0 ? (
                      <p className="text-gray-900">
                        Open
                      </p>
                    ) : null}

                    <div className="grid gap-2">
                      {appointmentsForHour.map(
                        (appointment) =>
                          appointmentCard(
                            appointment
                          )
                      )}

                      {blockedForHour.map((block) =>
                        blockedTimeCard(block)
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        ) : null}

        {!loading && viewMode === "week" ? (
          <section className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-gray-200">
            <h2 className="text-3xl font-bold mb-6">
              Week View —{" "}
              {selectedBarber?.name || "Staff"}
            </h2>

            <div className="grid gap-4">
              {weekDates.map((date, index) => {
                const items =
                  weekItemsForDate(date);

                return (
                  <div
                    key={date}
                    className="border rounded-xl p-4"
                  >
                    <h3 className="text-xl font-bold mb-3">
                      {DAYS[index]} — {date}
                    </h3>

                    {items.length === 0 ? (
                      <p className="text-gray-900">
                        No appointments or blocked
                        time.
                      </p>
                    ) : null}

                    <div className="grid gap-2">
                      {items.map((item) =>
                        item.type ===
                        "appointment"
                          ? appointmentCard(
                              item.data
                            )
                          : blockedTimeCard(
                              item.data
                            )
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        ) : null}
      </div>
    </main>
  );
}
