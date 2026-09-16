"use client";

import { useParams, useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import AdminUserBar from "../../../components/AdminUserBar";

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

function defaultRecurringEndDate() {
  const date = new Date();

  date.setMonth(
    date.getMonth() + 3
  );

  return localDateValue(date);
}

function weekdayValueForDate(
  dateString
) {
  if (!dateString) {
    const today =
      new Date().getDay();

    return today === 0
      ? 6
      : today - 1;
  }

  const date = new Date(
    `${dateString}T12:00:00`
  );

  const javascriptDay =
    date.getDay();

  return javascriptDay === 0
    ? 6
    : javascriptDay - 1;
}

export default function CalendarPage() {
  const params = useParams();
  const router = useRouter();

  const shopSlug = params.shop;

  const [
    currentUser,
    setCurrentUser,
  ] = useState(null);

  const [
    appointments,
    setAppointments,
  ] = useState([]);

  const [
    barbers,
    setBarbers,
  ] = useState([]);

  const [
    services,
    setServices,
  ] = useState([]);

  const [
    blockedTimes,
    setBlockedTimes,
  ] = useState([]);

  const [
    selectedDate,
    setSelectedDate,
  ] = useState(
    localDateValue()
  );

  const [
    selectedBarberId,
    setSelectedBarberId,
  ] = useState("");

  const [
    viewMode,
    setViewMode,
  ] = useState("day");

  const [
    movingAppointmentId,
    setMovingAppointmentId,
  ] = useState("");

  const [
    moveDate,
    setMoveDate,
  ] = useState(
    localDateValue()
  );

  const [
    moveTime,
    setMoveTime,
  ] = useState("09:00");

  const [
    savingMove,
    setSavingMove,
  ] = useState(false);

  const [
    showBlockForm,
    setShowBlockForm,
  ] = useState(false);

  const [
    blockMode,
    setBlockMode,
  ] = useState("one-time");

  const [
    blockReason,
    setBlockReason,
  ] = useState("Lunch");

  const [
    customBlockReason,
    setCustomBlockReason,
  ] = useState("");

  const [
    blockDate,
    setBlockDate,
  ] = useState(
    localDateValue()
  );

  const [
    blockStartTime,
    setBlockStartTime,
  ] = useState("12:00");

  const [
    blockEndTime,
    setBlockEndTime,
  ] = useState("12:30");

  const [
    recurringStartDate,
    setRecurringStartDate,
  ] = useState(
    localDateValue()
  );

  const [
    recurringEndDate,
    setRecurringEndDate,
  ] = useState(
    defaultRecurringEndDate()
  );

  const [
    recurringDays,
    setRecurringDays,
  ] = useState([
    weekdayValueForDate(
      localDateValue()
    ),
  ]);

  const [
    savingBlock,
    setSavingBlock,
  ] = useState(false);

  const [
    deletingBlockId,
    setDeletingBlockId,
  ] = useState("");

  const [
    deletingSeriesId,
    setDeletingSeriesId,
  ] = useState("");

  const [
    message,
    setMessage,
  ] = useState("");

  const [
    error,
    setError,
  ] = useState("");

  const [
    loading,
    setLoading,
  ] = useState(true);

  const currentUserRole = String(
    currentUser?.role || ""
  )
    .trim()
    .toLowerCase();

  const isOwner =
    currentUserRole === "owner";

  const isStaff =
    currentUserRole === "staff";

  const currentUserBarberId =
    String(
      currentUser?.barber_id || ""
    ).trim();

  function canManageBarber(
    barberId
  ) {
    if (isOwner) {
      return true;
    }

    if (!isStaff) {
      return false;
    }

    if (!currentUserBarberId) {
      return false;
    }

    return (
      String(barberId || "") ===
      currentUserBarberId
    );
  }

  function canModifyAppointment(
    appointment
  ) {
    return canManageBarber(
      appointment?.barber_id
    );
  }

  function canModifyBlockedTime(
    block
  ) {
    return canManageBarber(
      block?.barber_id
    );
  }

  const canManageSelectedBarber =
    canManageBarber(
      selectedBarberId
    );

  const loadData =
    useCallback(async () => {
      setLoading(true);
      setError("");

      try {
        const [
          meResponse,
          agendaResponse,
          blockedResponse,
        ] = await Promise.all([
          fetch(
            "/api/auth/me",
            {
              method: "GET",
              headers: {
                Accept:
                  "application/json",
              },
              cache: "no-store",
            }
          ),

          fetch(
            "/api/admin/agenda",
            {
              method: "GET",
              headers: {
                Accept:
                  "application/json",
              },
              cache: "no-store",
            }
          ),

          fetch(
            "/api/admin/blocked-times",
            {
              method: "GET",
              headers: {
                Accept:
                  "application/json",
              },
              cache: "no-store",
            }
          ),
        ]);

        if (
          meResponse.status === 401 ||
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

        const meData =
          await meResponse.json();

        const agendaData =
          await agendaResponse.json();

        const blockedData =
          await blockedResponse.json();

        if (!meResponse.ok) {
          throw new Error(
            meData?.error ||
              meData?.detail ||
              "Your account information could not be loaded."
          );
        }

        if (!agendaResponse.ok) {
          throw new Error(
            agendaData?.error ||
              agendaData?.detail ||
              "Calendar data could not be loaded."
          );
        }

        if (!blockedResponse.ok) {
          throw new Error(
            blockedData?.error ||
              blockedData?.detail ||
              "Blocked times could not be loaded."
          );
        }

        if (
          meData.shop_slug &&
          meData.shop_slug !==
            shopSlug
        ) {
          router.replace(
            `/${meData.shop_slug}/admin/calendar`
          );

          return;
        }

        if (
          agendaData.shop_slug &&
          agendaData.shop_slug !==
            shopSlug
        ) {
          router.replace(
            `/${agendaData.shop_slug}/admin/calendar`
          );

          return;
        }

        const loadedBarbers =
          agendaData.barbers || [];

        const loadedRole =
          String(
            meData?.role || ""
          )
            .trim()
            .toLowerCase();

        const loadedBarberId =
          String(
            meData?.barber_id || ""
          ).trim();

        setCurrentUser(
          meData
        );

        setAppointments(
          agendaData.appointments ||
            []
        );

        setBarbers(
          loadedBarbers
        );

        setServices(
          agendaData.services || []
        );

        setBlockedTimes(
          blockedData.blocked_times ||
            []
        );

        setSelectedBarberId(
          (currentValue) => {
            if (
              currentValue &&
              loadedBarbers.some(
                (barber) =>
                  barber.id ===
                  currentValue
              )
            ) {
              return currentValue;
            }

            if (
              loadedRole === "staff" &&
              loadedBarberId &&
              loadedBarbers.some(
                (barber) =>
                  barber.id ===
                  loadedBarberId
              )
            ) {
              return loadedBarberId;
            }

            return (
              loadedBarbers[0]?.id ||
              ""
            );
          }
        );
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

  function sameDay(
    value,
    date
  ) {
    return (
      datePart(value) === date
    );
  }

  function formatTime(value) {
    return new Date(
      value
    ).toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit",
    });
  }

  function serviceName(id) {
    return (
      services.find(
        (service) =>
          service.id === id
      )?.name || "Service"
    );
  }

  function getWeekDates(
    dateString
  ) {
    const date = new Date(
      `${dateString}T12:00:00`
    );

    const day =
      date.getDay();

    const sunday =
      new Date(date);

    sunday.setDate(
      date.getDate() - day
    );

    return Array.from(
      { length: 7 },
      (_, index) => {
        const weekDate =
          new Date(sunday);

        weekDate.setDate(
          sunday.getDate() +
            index
        );

        return localDateValue(
          weekDate
        );
      }
    );
  }

  function startMove(
    appointment
  ) {
    if (
      !canModifyAppointment(
        appointment
      )
    ) {
      setError(
        "Employees may modify only their own appointments."
      );

      return;
    }

    setMovingAppointmentId(
      appointment.id
    );

    setMoveDate(
      datePart(
        appointment.start_datetime
      )
    );

    setMoveTime(
      timePart(
        appointment.start_datetime
      ) || "09:00"
    );

    setMessage("");
    setError("");
  }

  function cancelMove() {
    setMovingAppointmentId(
      ""
    );

    setSavingMove(false);
    setError("");
  }

  async function saveMove(
    appointmentId
  ) {
    const appointment =
      appointments.find(
        (item) =>
          item.id === appointmentId
      );

    if (
      !appointment ||
      !canModifyAppointment(
        appointment
      )
    ) {
      setError(
        "Employees may modify only their own appointments."
      );

      return;
    }

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
      const response =
        await fetch(
          `/api/admin/appointments/${encodeURIComponent(
            appointmentId
          )}/reschedule`,
          {
            method: "PATCH",
            headers: {
              "Content-Type":
                "application/json",
              Accept:
                "application/json",
            },
            body: JSON.stringify({
              new_start_datetime:
                newStartDatetime,
            }),
          }
        );

      const data =
        await response.json();

      if (
        response.status === 401
      ) {
        router.replace("/login");
        return;
      }

      if (!response.ok) {
        throw new Error(
          data?.error ||
            data?.detail ||
            "The appointment could not be moved."
        );
      }

      setMovingAppointmentId(
        ""
      );

      setSelectedDate(
        moveDate
      );

      setMessage(
        "Appointment moved."
      );

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
    const appointment =
      appointments.find(
        (item) =>
          item.id === appointmentId
      );

    if (
      !appointment ||
      !canModifyAppointment(
        appointment
      )
    ) {
      setError(
        "Employees may modify only their own appointments."
      );

      return;
    }

    setMessage("");
    setError("");

    try {
      const response =
        await fetch(
          `/api/admin/appointments/${encodeURIComponent(
            appointmentId
          )}/status`,
          {
            method: "PATCH",
            headers: {
              "Content-Type":
                "application/json",
              Accept:
                "application/json",
            },
            body: JSON.stringify({
              status:
                appointmentStatus,
            }),
          }
        );

      const data =
        await response.json();

      if (
        response.status === 401
      ) {
        router.replace("/login");
        return;
      }

      if (!response.ok) {
        throw new Error(
          data?.error ||
            data?.detail ||
            "Appointment status could not be updated."
        );
      }

      setMessage(
        `Appointment marked ${
          STATUS_LABELS[
            appointmentStatus
          ]
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
    if (
      !canManageSelectedBarber
    ) {
      setError(
        "Employees may block time only on their own schedule."
      );

      return;
    }

    setBlockMode(
      "one-time"
    );

    setBlockDate(
      selectedDate
    );

    setRecurringStartDate(
      selectedDate
    );

    setRecurringEndDate(
      defaultRecurringEndDate()
    );

    setBlockStartTime(
      "12:00"
    );

    setBlockEndTime(
      "12:30"
    );

    setBlockReason(
      "Lunch"
    );

    setCustomBlockReason(
      ""
    );

    setRecurringDays([
      weekdayValueForDate(
        selectedDate
      ),
    ]);

    setShowBlockForm(
      true
    );

    setMessage("");
    setError("");
  }

  function closeBlockForm() {
    setShowBlockForm(
      false
    );

    setSavingBlock(
      false
    );

    setError("");
  }

  function toggleRecurringDay(
    dayValue
  ) {
    setRecurringDays(
      (currentDays) => {
        if (
          currentDays.includes(
            dayValue
          )
        ) {
          return currentDays.filter(
            (day) =>
              day !== dayValue
          );
        }

        return [
          ...currentDays,
          dayValue,
        ].sort(
          (a, b) => a - b
        );
      }
    );
  }

  function handleRecurringStartDateChange(
    nextDate
  ) {
    setRecurringStartDate(
      nextDate
    );

    setRecurringDays(
      (currentDays) => {
        if (
          currentDays.length <= 1
        ) {
          return [
            weekdayValueForDate(
              nextDate
            ),
          ];
        }

        return currentDays;
      }
    );
  }

  function finalBlockReason() {
    return blockReason ===
      "Other"
      ? customBlockReason.trim()
      : blockReason;
  }

  async function saveOneTimeBlockedTime() {
    if (
      !canManageBarber(
        selectedBarberId
      )
    ) {
      setError(
        "Employees may block time only on their own schedule."
      );

      return false;
    }

    const reason =
      finalBlockReason();

    if (!reason) {
      setError(
        "Please enter a reason."
      );

      return false;
    }

    const startDatetime =
      `${blockDate}T${blockStartTime}:00`;

    const endDatetime =
      `${blockDate}T${blockEndTime}:00`;

    const response =
      await fetch(
        "/api/admin/blocked-times",
        {
          method: "POST",

          headers: {
            "Content-Type":
              "application/json",

            Accept:
              "application/json",
          },

          body: JSON.stringify({
            barber_id:
              selectedBarberId,

            reason,

            start_datetime:
              startDatetime,

            end_datetime:
              endDatetime,
          }),
        }
      );

    const data =
      await response.json();

    if (
      response.status === 401
    ) {
      router.replace(
        "/login"
      );

      return false;
    }

    if (!response.ok) {
      throw new Error(
        data?.error ||
          data?.detail ||
          "Blocked time could not be created."
      );
    }

    setSelectedDate(
      blockDate
    );

    setMessage(
      "Time blocked."
    );

    return true;
  }

  async function saveRecurringBlockedTime() {
    if (
      !canManageBarber(
        selectedBarberId
      )
    ) {
      setError(
        "Employees may block time only on their own schedule."
      );

      return false;
    }

    const reason =
      finalBlockReason();

    if (!reason) {
      setError(
        "Please enter a reason."
      );

      return false;
    }

    if (
      recurringDays.length ===
      0
    ) {
      setError(
        "Choose at least one day of the week."
      );

      return false;
    }

    const response =
      await fetch(
        "/api/admin/blocked-times/recurring",
        {
          method: "POST",

          headers: {
            "Content-Type":
              "application/json",

            Accept:
              "application/json",
          },

          body: JSON.stringify({
            barber_id:
              selectedBarberId,

            reason,

            start_date:
              recurringStartDate,

            end_date:
              recurringEndDate,

            start_time:
              `${blockStartTime}:00`,

            end_time:
              `${blockEndTime}:00`,

            weekdays:
              recurringDays,
          }),
        }
      );

    const data =
      await response.json();

    if (
      response.status === 401
    ) {
      router.replace(
        "/login"
      );

      return false;
    }

    if (!response.ok) {
      throw new Error(
        data?.error ||
          data?.detail ||
          "Recurring blocked time could not be created."
      );
    }

    const created =
      data?.occurrences_created ||
      0;

    setSelectedDate(
      recurringStartDate
    );

    setMessage(
      `Recurring blocked time created (${created} occurrences).`
    );

    return true;
  }

  async function saveBlockedTime() {
    if (
      !canManageBarber(
        selectedBarberId
      )
    ) {
      setError(
        "Employees may block time only on their own schedule."
      );

      return;
    }

    if (
      !selectedBarberId ||
      !blockStartTime ||
      !blockEndTime ||
      savingBlock
    ) {
      return;
    }

    setSavingBlock(
      true
    );

    setMessage("");
    setError("");

    try {
      let saved = false;

      if (
        blockMode ===
        "recurring"
      ) {
        saved =
          await saveRecurringBlockedTime();
      } else {
        if (!blockDate) {
          setError(
            "Please choose a date."
          );

          return;
        }

        saved =
          await saveOneTimeBlockedTime();
      }

      if (saved) {
        setShowBlockForm(
          false
        );

        await loadData();
      }
    } catch (blockError) {
      setError(
        blockError instanceof Error
          ? blockError.message
          : "Blocked time could not be created."
      );
    } finally {
      setSavingBlock(
        false
      );
    }
  }

  async function deleteBlockedTime(
    blockedTimeId
  ) {
    if (deletingBlockId) {
      return;
    }

    const block =
      blockedTimes.find(
        (item) =>
          item.id ===
          blockedTimeId
      );

    if (
      !block ||
      !canModifyBlockedTime(
        block
      )
    ) {
      setError(
        "Employees may modify blocked time only on their own schedule."
      );

      return;
    }

    const confirmed =
      window.confirm(
        "Delete this blocked time?"
      );

    if (!confirmed) {
      return;
    }

    setDeletingBlockId(
      blockedTimeId
    );

    setMessage("");
    setError("");

    try {
      const response =
        await fetch(
          `/api/admin/blocked-times/${encodeURIComponent(
            blockedTimeId
          )}`,
          {
            method: "DELETE",

            headers: {
              Accept:
                "application/json",
            },
          }
        );

      const data =
        await response.json();

      if (
        response.status === 401
      ) {
        router.replace(
          "/login"
        );

        return;
      }

      if (!response.ok) {
        throw new Error(
          data?.error ||
            data?.detail ||
            "Blocked time could not be deleted."
        );
      }

      setMessage(
        "Blocked time deleted."
      );

      await loadData();
    } catch (deleteError) {
      setError(
        deleteError instanceof Error
          ? deleteError.message
          : "Blocked time could not be deleted."
      );
    } finally {
      setDeletingBlockId(
        ""
      );
    }
  }

  async function deleteBlockedTimeSeries(
    seriesId
  ) {
    if (
      !seriesId ||
      deletingSeriesId
    ) {
      return;
    }

    const seriesBlocks =
      blockedTimes.filter(
        (block) =>
          block.series_id ===
          seriesId
      );

    if (
      seriesBlocks.length === 0 ||
      seriesBlocks.some(
        (block) =>
          !canModifyBlockedTime(
            block
          )
      )
    ) {
      setError(
        "Employees may modify blocked time only on their own schedule."
      );

      return;
    }

    const confirmed =
      window.confirm(
        "Delete every remaining blocked time in this recurring series?"
      );

    if (!confirmed) {
      return;
    }

    setDeletingSeriesId(
      seriesId
    );

    setMessage("");
    setError("");

    try {
      const response =
        await fetch(
          `/api/admin/blocked-time-series/${encodeURIComponent(
            seriesId
          )}`,
          {
            method: "DELETE",

            headers: {
              Accept:
                "application/json",
            },
          }
        );

      const data =
        await response.json();

      if (
        response.status === 401
      ) {
        router.replace(
          "/login"
        );

        return;
      }

      if (!response.ok) {
        throw new Error(
          data?.error ||
            data?.detail ||
            "Recurring series could not be deleted."
        );
      }

      setMessage(
        `Recurring series deleted (${
          data?.occurrences_deleted ||
          0
        } occurrences).`
      );

      await loadData();
    } catch (deleteError) {
      setError(
        deleteError instanceof Error
          ? deleteError.message
          : "Recurring series could not be deleted."
      );
    } finally {
      setDeletingSeriesId(
        ""
      );
    }
  }

  const selectedBarber =
    barbers.find(
      (barber) =>
        barber.id ===
        selectedBarberId
    );

  const dayAppointments =
    useMemo(() => {
      return appointments
        .filter(
          (appointment) =>
            appointment.barber_id ===
            selectedBarberId
        )
        .filter(
          (appointment) =>
            sameDay(
              appointment.start_datetime,
              selectedDate
            )
        )
        .sort(
          (a, b) =>
            new Date(
              a.start_datetime
            ) -
            new Date(
              b.start_datetime
            )
        );
    }, [
      appointments,
      selectedBarberId,
      selectedDate,
    ]);

  const dayBlockedTimes =
    useMemo(() => {
      return blockedTimes
        .filter(
          (block) =>
            block.barber_id ===
            selectedBarberId
        )
        .filter(
          (block) =>
            sameDay(
              block.start_datetime,
              selectedDate
            )
        )
        .sort(
          (a, b) =>
            new Date(
              a.start_datetime
            ) -
            new Date(
              b.start_datetime
            )
        );
    }, [
      blockedTimes,
      selectedBarberId,
      selectedDate,
    ]);

  const weekDates =
    useMemo(
      () =>
        getWeekDates(
          selectedDate
        ),
      [selectedDate]
    );

  function appointmentItemsForHour(
    hourText
  ) {
    const hour =
      Number(
        hourText.split(":")[0]
      );

    return dayAppointments.filter(
      (appointment) =>
        new Date(
          appointment.start_datetime
        ).getHours() === hour
    );
  }

  function blockedItemsForHour(
    hourText
  ) {
    const hour =
      Number(
        hourText.split(":")[0]
      );

    return dayBlockedTimes.filter(
      (block) =>
        new Date(
          block.start_datetime
        ).getHours() === hour
    );
  }

  function weekItemsForDate(
    date
  ) {
    const appointmentItems =
      appointments
        .filter(
          (appointment) =>
            appointment.barber_id ===
            selectedBarberId
        )
        .filter(
          (appointment) =>
            sameDay(
              appointment.start_datetime,
              date
            )
        )
        .map(
          (appointment) => ({
            type:
              "appointment",

            id:
              appointment.id,

            time:
              appointment.start_datetime,

            data:
              appointment,
          })
        );

    const blockedItems =
      blockedTimes
        .filter(
          (block) =>
            block.barber_id ===
            selectedBarberId
        )
        .filter(
          (block) =>
            sameDay(
              block.start_datetime,
              date
            )
        )
        .map(
          (block) => ({
            type:
              "blocked",

            id:
              block.id,

            time:
              block.start_datetime,

            data:
              block,
          })
        );

    return [
      ...appointmentItems,
      ...blockedItems,
    ].sort(
      (a, b) =>
        new Date(a.time) -
        new Date(b.time)
    );
  }

  function renderAppointmentCard(
    appointment
  ) {
    const canModify =
      canModifyAppointment(
        appointment
      );

    const isMoving =
      movingAppointmentId ===
      appointment.id;

    const status =
      appointment.status ||
      "confirmed";

    return (
      <div
        key={appointment.id}
        className={`rounded-xl border p-3 ${
          STATUS_STYLES[status] ||
          STATUS_STYLES.confirmed
        }`}
      >
        <div className="flex flex-col gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <p className="font-extrabold text-gray-950">
                {formatTime(
                  appointment.start_datetime
                )}
              </p>

              <span className="rounded-full bg-white/70 px-2 py-1 text-xs font-bold text-gray-700">
                {STATUS_LABELS[
                  status
                ] || status}
              </span>
            </div>

            <p className="mt-1 font-bold text-gray-900">
              {appointment.customer_name ||
                "Customer"}
            </p>

            <p className="text-sm text-gray-700">
              {serviceName(
                appointment.service_id
              )}
            </p>

            {appointment.customer_phone && (
              <p className="mt-1 text-sm text-gray-600">
                {
                  appointment.customer_phone
                }
              </p>
            )}
          </div>

          {canModify && (
            <>
              {isMoving ? (
                <div className="rounded-xl border border-blue-200 bg-white p-3 space-y-3">
                  <p className="font-bold text-gray-900">
                    Move appointment
                  </p>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <div>
                      <label className="mb-1 block text-xs font-bold text-gray-700">
                        Date
                      </label>

                      <input
                        type="date"
                        value={
                          moveDate
                        }
                        onChange={(
                          event
                        ) =>
                          setMoveDate(
                            event.target
                              .value
                          )
                        }
                        className="w-full rounded-lg border border-gray-300 bg-white p-2"
                      />
                    </div>

                    <div>
                      <label className="mb-1 block text-xs font-bold text-gray-700">
                        Time
                      </label>

                      <input
                        type="time"
                        value={
                          moveTime
                        }
                        onChange={(
                          event
                        ) =>
                          setMoveTime(
                            event.target
                              .value
                          )
                        }
                        className="w-full rounded-lg border border-gray-300 bg-white p-2"
                      />
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() =>
                        saveMove(
                          appointment.id
                        )
                      }
                      disabled={
                        savingMove
                      }
                      className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-bold text-white hover:bg-blue-700 disabled:opacity-50"
                    >
                      {savingMove
                        ? "Saving..."
                        : "Save Move"}
                    </button>

                    <button
                      type="button"
                      onClick={
                        cancelMove
                      }
                      disabled={
                        savingMove
                      }
                      className="rounded-lg bg-gray-200 px-3 py-2 text-sm font-bold text-gray-800 hover:bg-gray-300"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      startMove(
                        appointment
                      )
                    }
                    className="rounded-lg bg-white px-3 py-2 text-sm font-bold text-blue-700 shadow-sm hover:bg-blue-50"
                  >
                    Move
                  </button>

                  {status !==
                    "confirmed" && (
                    <button
                      type="button"
                      onClick={() =>
                        updateAppointmentStatus(
                          appointment.id,
                          "confirmed"
                        )
                      }
                      className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-bold text-white hover:bg-blue-700"
                    >
                      Confirm
                    </button>
                  )}

                  {status !==
                    "completed" && (
                    <button
                      type="button"
                      onClick={() =>
                        updateAppointmentStatus(
                          appointment.id,
                          "completed"
                        )
                      }
                      className="rounded-lg bg-green-600 px-3 py-2 text-sm font-bold text-white hover:bg-green-700"
                    >
                      Complete
                    </button>
                  )}

                  {status !==
                    "no_show" && (
                    <button
                      type="button"
                      onClick={() =>
                        updateAppointmentStatus(
                          appointment.id,
                          "no_show"
                        )
                      }
                      className="rounded-lg bg-yellow-500 px-3 py-2 text-sm font-bold text-gray-950 hover:bg-yellow-600"
                    >
                      No-show
                    </button>
                  )}

                  {status !==
                    "canceled" && (
                    <button
                      type="button"
                      onClick={() =>
                        updateAppointmentStatus(
                          appointment.id,
                          "canceled"
                        )
                      }
                      className="rounded-lg bg-red-600 px-3 py-2 text-sm font-bold text-white hover:bg-red-700"
                    >
                      Cancel Appointment
                    </button>
                  )}
                </div>
              )}
            </>
          )}

          {!canModify &&
            isStaff && (
              <p className="text-xs font-semibold text-gray-500">
                View only — this appointment belongs to another staff member.
              </p>
            )}
        </div>
      </div>
    );
  }

  function renderBlockedTimeCard(
    block
  ) {
    const canModify =
      canModifyBlockedTime(
        block
      );

    return (
      <div
        key={block.id}
        className="rounded-xl border border-gray-300 bg-gray-100 p-3"
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="font-extrabold text-gray-900">
              {formatTime(
                block.start_datetime
              )}{" "}
              –{" "}
              {formatTime(
                block.end_datetime
              )}
            </p>

            <p className="mt-1 font-bold text-gray-800">
              {block.reason ||
                "Blocked"}
            </p>

            {block.series_id && (
              <p className="mt-1 text-xs font-semibold text-gray-500">
                Recurring blocked time
              </p>
            )}
          </div>

          {canModify && (
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() =>
                  deleteBlockedTime(
                    block.id
                  )
                }
                disabled={
                  deletingBlockId ===
                  block.id
                }
                className="rounded-lg bg-red-600 px-3 py-2 text-sm font-bold text-white hover:bg-red-700 disabled:opacity-50"
              >
                {deletingBlockId ===
                block.id
                  ? "Deleting..."
                  : "Delete"}
              </button>

              {block.series_id && (
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
                  className="rounded-lg bg-gray-800 px-3 py-2 text-sm font-bold text-white hover:bg-gray-900 disabled:opacity-50"
                >
                  {deletingSeriesId ===
                  block.series_id
                    ? "Deleting Series..."
                    : "Delete Series"}
                </button>
              )}
            </div>
          )}

          {!canModify &&
            isStaff && (
              <p className="text-xs font-semibold text-gray-500">
                View only
              </p>
            )}
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <main className="min-h-screen bg-emerald-50 p-4 sm:p-8">
        <div className="mx-auto max-w-5xl">
          <div className="rounded-3xl border border-emerald-200 bg-white p-6 shadow-lg">
            <p className="font-bold text-gray-700">
              Loading calendar...
            </p>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-emerald-50 p-4 sm:p-8">
      <div className="mx-auto max-w-5xl space-y-6">
        <AdminUserBar />

        <section className="rounded-3xl border border-emerald-200 bg-gradient-to-r from-emerald-100 via-green-50 to-white p-6 shadow-lg">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="mb-2 text-sm font-extrabold uppercase tracking-widest text-emerald-700">
                {displayShopName(
                  shopSlug
                )}
              </p>

              <h1 className="text-5xl font-extrabold tracking-tight text-gray-950">
                Calendar
              </h1>

              <p className="mt-2 text-lg text-gray-700">
                {isStaff
                  ? "View the shop schedule and manage your own appointments and blocked time."
                  : "View appointments and manage blocked time."}
              </p>
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() =>
                  router.push(
                    `/${shopSlug}/admin`
                  )
                }
                className="rounded-xl bg-blue-600 px-5 py-3 font-bold text-white shadow hover:bg-blue-700"
              >
                Admin Home
              </button>

              {canManageSelectedBarber && (
                <button
                  type="button"
                  onClick={
                    openBlockForm
                  }
                  className="rounded-xl bg-emerald-700 px-5 py-3 font-bold text-white shadow hover:bg-emerald-800"
                >
                  + Block Time
                </button>
              )}
            </div>
          </div>
        </section>

        {message && (
          <div className="rounded-2xl border border-green-200 bg-green-100 p-4 font-bold text-green-800">
            {message}
          </div>
        )}

        {error && (
          <div className="rounded-2xl border border-red-200 bg-red-50 p-4 font-bold text-red-800">
            {error}
          </div>
        )}

        <section className="rounded-3xl border border-emerald-200 bg-white p-6 shadow-lg">
          <h2 className="mb-4 text-2xl font-extrabold text-gray-950">
            Filters
          </h2>

          <div className="grid gap-4 md:grid-cols-3">
            <div>
              <label className="mb-1 block text-sm font-bold text-gray-800">
                View
              </label>

              <select
                value={
                  viewMode
                }
                onChange={(
                  event
                ) =>
                  setViewMode(
                    event.target
                      .value
                  )
                }
                className="w-full rounded-xl border border-emerald-200 bg-white p-3"
              >
                <option value="day">
                  Day
                </option>

                <option value="week">
                  Week
                </option>
              </select>
            </div>

            <div>
              <label className="mb-1 block text-sm font-bold text-gray-800">
                Date
              </label>

              <input
                type="date"
                value={
                  selectedDate
                }
                onChange={(
                  event
                ) => {
                  setSelectedDate(
                    event.target
                      .value
                  );

                  setMessage("");
                  setError("");
                }}
                className="w-full rounded-xl border border-emerald-200 bg-white p-3"
              />
            </div>

            <div>
              <label className="mb-1 block text-sm font-bold text-gray-800">
                Staff
              </label>

              <select
                value={
                  selectedBarberId
                }
                onChange={(
                  event
                ) => {
                  setSelectedBarberId(
                    event.target
                      .value
                  );

                  setShowBlockForm(
                    false
                  );

                  setMovingAppointmentId(
                    ""
                  );

                  setMessage("");
                  setError("");
                }}
                className="w-full rounded-xl border border-emerald-200 bg-white p-3"
              >
                {barbers.map(
                  (barber) => (
                    <option
                      key={
                        barber.id
                      }
                      value={
                        barber.id
                      }
                    >
                      {barber.name}
                    </option>
                  )
                )}
              </select>
            </div>
          </div>

          {isStaff &&
            selectedBarberId &&
            !canManageSelectedBarber && (
              <div className="mt-4 rounded-xl border border-blue-200 bg-blue-50 p-3 text-sm font-semibold text-blue-800">
                You can view this staff member&apos;s schedule, but only they or the shop owner can make changes to it.
              </div>
            )}

          {isStaff &&
            !currentUserBarberId && (
              <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm font-semibold text-amber-800">
                Your login is not linked to a staff/provider record, so this calendar is view-only.
              </div>
            )}
        </section>

        {showBlockForm &&
          canManageSelectedBarber && (
            <section className="rounded-3xl border border-emerald-200 bg-white p-6 shadow-lg">
              <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-sm font-extrabold uppercase tracking-widest text-emerald-700">
                    Availability
                  </p>

                  <h2 className="text-3xl font-extrabold text-gray-950">
                    Block Time
                  </h2>

                  <p className="mt-1 text-gray-600">
                    {selectedBarber
                      ? `For ${selectedBarber.name}`
                      : "Choose a staff member."}
                  </p>
                </div>

                <button
                  type="button"
                  onClick={
                    closeBlockForm
                  }
                  className="rounded-xl bg-gray-200 px-4 py-2 font-bold text-gray-800 hover:bg-gray-300"
                >
                  Close
                </button>
              </div>

              <div className="mb-5 grid grid-cols-2 gap-2 rounded-2xl bg-gray-100 p-1">
                <button
                  type="button"
                  onClick={() =>
                    setBlockMode(
                      "one-time"
                    )
                  }
                  className={`rounded-xl px-4 py-3 font-bold ${
                    blockMode ===
                    "one-time"
                      ? "bg-white text-emerald-800 shadow"
                      : "text-gray-600"
                  }`}
                >
                  One Time
                </button>

                <button
                  type="button"
                  onClick={() =>
                    setBlockMode(
                      "recurring"
                    )
                  }
                  className={`rounded-xl px-4 py-3 font-bold ${
                    blockMode ===
                    "recurring"
                      ? "bg-white text-emerald-800 shadow"
                      : "text-gray-600"
                  }`}
                >
                  Recurring
                </button>
              </div>

              <div className="space-y-4">
                {blockMode ===
                "one-time" ? (
                  <div>
                    <label className="mb-1 block text-sm font-bold text-gray-800">
                      Date
                    </label>

                    <input
                      type="date"
                      value={
                        blockDate
                      }
                      onChange={(
                        event
                      ) =>
                        setBlockDate(
                          event.target
                            .value
                        )
                      }
                      className="w-full rounded-xl border border-emerald-200 bg-white p-3"
                    />
                  </div>
                ) : (
                  <>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div>
                        <label className="mb-1 block text-sm font-bold text-gray-800">
                          Starts
                        </label>

                        <input
                          type="date"
                          value={
                            recurringStartDate
                          }
                          onChange={(
                            event
                          ) =>
                            handleRecurringStartDateChange(
                              event.target
                                .value
                            )
                          }
                          className="w-full rounded-xl border border-emerald-200 bg-white p-3"
                        />
                      </div>

                      <div>
                        <label className="mb-1 block text-sm font-bold text-gray-800">
                          Ends
                        </label>

                        <input
                          type="date"
                          value={
                            recurringEndDate
                          }
                          onChange={(
                            event
                          ) =>
                            setRecurringEndDate(
                              event.target
                                .value
                            )
                          }
                          className="w-full rounded-xl border border-emerald-200 bg-white p-3"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="mb-2 block text-sm font-bold text-gray-800">
                        Repeat on
                      </label>

                      <div className="flex flex-wrap gap-2">
                        {RECURRING_DAYS.map(
                          (day) => {
                            const selected =
                              recurringDays.includes(
                                day.value
                              );

                            return (
                              <button
                                key={
                                  day.value
                                }
                                type="button"
                                onClick={() =>
                                  toggleRecurringDay(
                                    day.value
                                  )
                                }
                                className={`rounded-xl border px-4 py-2 font-bold ${
                                  selected
                                    ? "border-emerald-700 bg-emerald-700 text-white"
                                    : "border-gray-300 bg-white text-gray-700"
                                }`}
                              >
                                {
                                  day.label
                                }
                              </button>
                            );
                          }
                        )}
                      </div>
                    </div>
                  </>
                )}

                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="mb-1 block text-sm font-bold text-gray-800">
                      Start time
                    </label>

                    <input
                      type="time"
                      value={
                        blockStartTime
                      }
                      onChange={(
                        event
                      ) =>
                        setBlockStartTime(
                          event.target
                            .value
                        )
                      }
                      className="w-full rounded-xl border border-emerald-200 bg-white p-3"
                    />
                  </div>

                  <div>
                    <label className="mb-1 block text-sm font-bold text-gray-800">
                      End time
                    </label>

                    <input
                      type="time"
                      value={
                        blockEndTime
                      }
                      onChange={(
                        event
                      ) =>
                        setBlockEndTime(
                          event.target
                            .value
                        )
                      }
                      className="w-full rounded-xl border border-emerald-200 bg-white p-3"
                    />
                  </div>
                </div>

                <div>
                  <label className="mb-1 block text-sm font-bold text-gray-800">
                    Reason
                  </label>

                  <select
                    value={
                      blockReason
                    }
                    onChange={(
                      event
                    ) =>
                      setBlockReason(
                        event.target
                          .value
                      )
                    }
                    className="w-full rounded-xl border border-emerald-200 bg-white p-3"
                  >
                    {BLOCK_REASON_OPTIONS.map(
                      (reason) => (
                        <option
                          key={
                            reason
                          }
                          value={
                            reason
                          }
                        >
                          {reason}
                        </option>
                      )
                    )}
                  </select>
                </div>

                {blockReason ===
                  "Other" && (
                  <div>
                    <label className="mb-1 block text-sm font-bold text-gray-800">
                      Custom reason
                    </label>

                    <input
                      type="text"
                      value={
                        customBlockReason
                      }
                      onChange={(
                        event
                      ) =>
                        setCustomBlockReason(
                          event.target
                            .value
                        )
                      }
                      placeholder="Reason"
                      className="w-full rounded-xl border border-emerald-200 bg-white p-3"
                    />
                  </div>
                )}

                <div className="flex flex-wrap gap-2 pt-2">
                  <button
                    type="button"
                    onClick={
                      saveBlockedTime
                    }
                    disabled={
                      savingBlock
                    }
                    className="rounded-xl bg-emerald-700 px-5 py-3 font-bold text-white shadow hover:bg-emerald-800 disabled:opacity-50"
                  >
                    {savingBlock
                      ? "Saving..."
                      : blockMode ===
                          "recurring"
                        ? "Create Recurring Block"
                        : "Block Time"}
                  </button>

                  <button
                    type="button"
                    onClick={
                      closeBlockForm
                    }
                    disabled={
                      savingBlock
                    }
                    className="rounded-xl bg-gray-200 px-5 py-3 font-bold text-gray-800 hover:bg-gray-300"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </section>
          )}

        {viewMode ===
        "day" ? (
          <section className="rounded-3xl border border-emerald-200 bg-white p-6 shadow-lg">
            <h2 className="mb-4 text-2xl font-extrabold text-gray-950">
              Day View —{" "}
              {selectedBarber?.name ||
                "Staff"}{" "}
              — {selectedDate}
            </h2>

            <div className="space-y-2">
              {HOURS.map(
                (hour) => {
                  const appointmentItems =
                    appointmentItemsForHour(
                      hour
                    );

                  const blockedItems =
                    blockedItemsForHour(
                      hour
                    );

                  const hasItems =
                    appointmentItems.length >
                      0 ||
                    blockedItems.length >
                      0;

                  return (
                    <div
                      key={
                        hour
                      }
                      className="rounded-xl border border-emerald-100 bg-emerald-50/40 p-3"
                    >
                      <p className="mb-2 text-sm font-extrabold text-gray-900">
                        {hour}
                      </p>

                      {!hasItems && (
                        <p className="text-sm text-gray-500">
                          Open
                        </p>
                      )}

                      <div className="space-y-2">
                        {blockedItems.map(
                          (
                            block
                          ) =>
                            renderBlockedTimeCard(
                              block
                            )
                        )}

                        {appointmentItems.map(
                          (
                            appointment
                          ) =>
                            renderAppointmentCard(
                              appointment
                            )
                        )}
                      </div>
                    </div>
                  );
                }
              )}
            </div>
          </section>
        ) : (
          <section className="rounded-3xl border border-emerald-200 bg-white p-6 shadow-lg">
            <h2 className="mb-4 text-2xl font-extrabold text-gray-950">
              Week View —{" "}
              {selectedBarber?.name ||
                "Staff"}
            </h2>

            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              {weekDates.map(
                (date) => {
                  const items =
                    weekItemsForDate(
                      date
                    );

                  const dateObject =
                    new Date(
                      `${date}T12:00:00`
                    );

                  return (
                    <div
                      key={
                        date
                      }
                      className="rounded-2xl border border-emerald-200 bg-emerald-50/40 p-4"
                    >
                      <div className="mb-3">
                        <p className="font-extrabold text-gray-950">
                          {
                            DAYS[
                              dateObject.getDay()
                            ]
                          }
                        </p>

                        <p className="text-sm text-gray-600">
                          {date}
                        </p>
                      </div>

                      {items.length ===
                      0 ? (
                        <p className="text-sm text-gray-500">
                          No appointments or blocked time.
                        </p>
                      ) : (
                        <div className="space-y-2">
                          {items.map(
                            (
                              item
                            ) => {
                              if (
                                item.type ===
                                "blocked"
                              ) {
                                return renderBlockedTimeCard(
                                  item.data
                                );
                              }

                              return renderAppointmentCard(
                                item.data
                              );
                            }
                          )}
                        </div>
                      )}
                    </div>
                  );
                }
              )}
            </div>
          </section>
        )}

        <div className="pb-4">
          <button
            type="button"
            onClick={() =>
              router.push(
                `/${shopSlug}/admin`
              )
            }
            className="rounded-xl bg-blue-600 px-5 py-3 font-bold text-white shadow hover:bg-blue-700"
          >
            Admin Home
          </button>
        </div>
      </div>
    </main>
  );
}
