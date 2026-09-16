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

function normalizePhone(value) {
  return String(value || "")
    .replace(/\D/g, "");
}

function customerKey(
  name,
  phone
) {
  const cleanPhone =
    normalizePhone(phone);

  if (cleanPhone) {
    return `phone:${cleanPhone}`;
  }

  return `name:${String(
    name || ""
  )
    .trim()
    .toLowerCase()}`;
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

  /*
   * NEW APPOINTMENT
   */

  const [
    showAppointmentForm,
    setShowAppointmentForm,
  ] = useState(false);

  const [
    appointmentCustomerMode,
    setAppointmentCustomerMode,
  ] = useState("existing");

  const [
    customerSearch,
    setCustomerSearch,
  ] = useState("");

  const [
    selectedCustomerKey,
    setSelectedCustomerKey,
  ] = useState("");

  const [
    appointmentCustomerName,
    setAppointmentCustomerName,
  ] = useState("");

  const [
    appointmentCustomerPhone,
    setAppointmentCustomerPhone,
  ] = useState("");

  const [
    appointmentServiceId,
    setAppointmentServiceId,
  ] = useState("");

  const [
    appointmentDate,
    setAppointmentDate,
  ] = useState(
    localDateValue()
  );

  const [
    appointmentTime,
    setAppointmentTime,
  ] = useState("09:00");

  const [
    appointmentNotes,
    setAppointmentNotes,
  ] = useState("");

  const [
    savingAppointment,
    setSavingAppointment,
  ] = useState(false);

  /*
   * MOVE APPOINTMENT
   */

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

  /*
   * BLOCKED TIME
   */

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

  /*
   * CURRENT USER / PERMISSIONS
   */

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

  /*
   * LOAD CALENDAR
   */

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
          agendaResponse.status ===
            401 ||
          blockedResponse.status ===
            401
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
            meData?.detail ||
              meData?.error ||
              "Your account could not be loaded."
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

        const userShopSlug =
          String(
            meData?.shop_slug || ""
          )
            .trim()
            .toLowerCase();

        if (
          !userShopSlug ||
          userShopSlug !== shopSlug
        ) {
          if (userShopSlug) {
            router.replace(
              `/${userShopSlug}/admin/calendar`
            );
          } else {
            router.replace("/login");
          }

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
              loadedRole ===
                "staff" &&
              loadedBarberId &&
              loadedBarbers.some(
                (barber) =>
                  String(
                    barber.id
                  ) ===
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

  /*
   * CUSTOMER LIST
   *
   * ChairTime's customer history is currently
   * appointment-based. Build a quick customer
   * picker from the shop's existing appointments.
   */

  const existingCustomers =
    useMemo(() => {
      const customerMap =
        new Map();

      appointments.forEach(
        (appointment) => {
          const name =
            String(
              appointment.customer_name ||
                ""
            ).trim();

          const phone =
            String(
              appointment.customer_phone ||
                ""
            ).trim();

          if (!name && !phone) {
            return;
          }

          const key =
            customerKey(
              name,
              phone
            );

          const existing =
            customerMap.get(key);

          const appointmentTime =
            new Date(
              appointment.start_datetime
            ).getTime();

          const existingTime =
            existing
              ? new Date(
                  existing.lastAppointment
                ).getTime()
              : 0;

          if (
            !existing ||
            appointmentTime >
              existingTime
          ) {
            customerMap.set(
              key,
              {
                key,
                name,
                phone,
                customerNotes:
                  appointment.customer_notes ||
                  "",
                customerTags:
                  appointment.customer_tags ||
                  "",
                lastAppointment:
                  appointment.start_datetime,
              }
            );
          }
        }
      );

      return Array.from(
        customerMap.values()
      ).sort((a, b) =>
        String(a.name).localeCompare(
          String(b.name)
        )
      );
    }, [appointments]);

  const filteredCustomers =
    useMemo(() => {
      const search =
        String(
          customerSearch || ""
        )
          .trim()
          .toLowerCase();

      if (!search) {
        return existingCustomers.slice(
          0,
          8
        );
      }

      const searchPhone =
        normalizePhone(search);

      return existingCustomers
        .filter((customer) => {
          const name =
            String(
              customer.name || ""
            ).toLowerCase();

          const phone =
            normalizePhone(
              customer.phone
            );

          return (
            name.includes(search) ||
            (searchPhone &&
              phone.includes(
                searchPhone
              ))
          );
        })
        .slice(0, 8);
    }, [
      customerSearch,
      existingCustomers,
    ]);

  const servicesForSelectedBarber =
    useMemo(() => {
      if (!selectedBarberId) {
        return [];
      }

      return services.filter(
        (service) => {
          const serviceBarberId =
            String(
              service.barber_id || ""
            ).trim();

          if (!serviceBarberId) {
            return true;
          }

          return (
            serviceBarberId ===
            String(
              selectedBarberId
            )
          );
        }
      );
    }, [
      services,
      selectedBarberId,
    ]);

  function resetAppointmentForm() {
    setAppointmentCustomerMode(
      existingCustomers.length
        ? "existing"
        : "new"
    );

    setCustomerSearch("");
    setSelectedCustomerKey("");
    setAppointmentCustomerName("");
    setAppointmentCustomerPhone("");

    setAppointmentServiceId(
      servicesForSelectedBarber[
        0
      ]?.id || ""
    );

    setAppointmentDate(
      selectedDate
    );

    setAppointmentTime(
      "09:00"
    );

    setAppointmentNotes("");
  }

  function openAppointmentForm(
    time = ""
  ) {
    if (
      !selectedBarberId ||
      !canManageSelectedBarber
    ) {
      return;
    }

    resetAppointmentForm();

    if (time) {
      setAppointmentTime(
        time
      );
    }

    setShowBlockForm(false);
    setShowAppointmentForm(true);
    setMessage("");
    setError("");
  }

  function closeAppointmentForm() {
    setShowAppointmentForm(false);
    setSavingAppointment(false);
    setError("");
  }

  function chooseExistingCustomer(
    customer
  ) {
    setSelectedCustomerKey(
      customer.key
    );

    setAppointmentCustomerName(
      customer.name
    );

    setAppointmentCustomerPhone(
      customer.phone
    );

    setCustomerSearch(
      customer.name ||
        customer.phone
    );
  }

  function startNewCustomer() {
    setAppointmentCustomerMode(
      "new"
    );

    setSelectedCustomerKey("");

    const searchValue =
      customerSearch.trim();

    const looksLikePhone =
      normalizePhone(
        searchValue
      ).length >= 7;

    if (looksLikePhone) {
      setAppointmentCustomerPhone(
        searchValue
      );

      setAppointmentCustomerName(
        ""
      );
    } else {
      setAppointmentCustomerName(
        searchValue
      );

      setAppointmentCustomerPhone(
        ""
      );
    }
  }

  function useExistingCustomerMode() {
    setAppointmentCustomerMode(
      "existing"
    );

    setSelectedCustomerKey("");
    setAppointmentCustomerName("");
    setAppointmentCustomerPhone("");
    setCustomerSearch("");
  }

  async function saveNewAppointment() {
    if (
      savingAppointment ||
      !selectedBarberId
    ) {
      return;
    }

    if (
      !canManageSelectedBarber
    ) {
      setError(
        "You can create appointments only for your own schedule."
      );

      return;
    }

    const customerName =
      appointmentCustomerName.trim();

    const customerPhone =
      appointmentCustomerPhone.trim();

    if (!customerName) {
      setError(
        "Enter the customer's name."
      );

      return;
    }

    if (!customerPhone) {
      setError(
        "Enter the customer's phone number."
      );

      return;
    }

    if (!appointmentServiceId) {
      setError(
        "Choose a service."
      );

      return;
    }

    if (
      !appointmentDate ||
      !appointmentTime
    ) {
      setError(
        "Choose the appointment date and time."
      );

      return;
    }

    setSavingAppointment(true);
    setMessage("");
    setError("");

    try {
      const response =
        await fetch(
          "/api/admin/appointments",
          {
            method: "POST",
            headers: {
              "Content-Type":
                "application/json",
              Accept:
                "application/json",
            },
            body: JSON.stringify({
              shop_slug:
                shopSlug,
              barber_id:
                selectedBarberId,
              service_id:
                appointmentServiceId,
              customer_name:
                customerName,
              customer_phone:
                customerPhone,
              customer_tags:
                null,
              customer_notes:
                null,
              notes:
                appointmentNotes.trim() ||
                null,
              start_datetime:
                `${appointmentDate}T${appointmentTime}:00`,
              stripe_setup_intent_id:
                null,
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

        return;
      }

      if (!response.ok) {
        throw new Error(
          data?.detail ||
            data?.error ||
            "The appointment could not be created."
        );
      }

      setShowAppointmentForm(
        false
      );

      setSelectedDate(
        appointmentDate
      );

      setMessage(
        `${customerName}'s appointment was booked.`
      );

      await loadData();
    } catch (appointmentError) {
      setError(
        appointmentError instanceof
          Error
          ? appointmentError.message
          : "The appointment could not be created."
      );
    } finally {
      setSavingAppointment(
        false
      );
    }
  }

  /*
   * MOVE APPOINTMENT
   */

  function startMove(
    appointment
  ) {
    if (
      !canModifyAppointment(
        appointment
      )
    ) {
      setError(
        "You can modify only your own appointments."
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
      )
    );

    setShowAppointmentForm(
      false
    );

    setShowBlockForm(false);
    setMessage("");
    setError("");
  }

  function cancelMove() {
    setMovingAppointmentId("");
    setSavingMove(false);
  }

  async function saveMove(
    appointmentId
  ) {
    if (savingMove) {
      return;
    }

    const appointment =
      appointments.find(
        (item) =>
          item.id ===
          appointmentId
      );

    if (
      !appointment ||
      !canModifyAppointment(
        appointment
      )
    ) {
      setError(
        "You can modify only your own appointments."
      );

      return;
    }

    if (!moveDate || !moveTime) {
      setError(
        "Choose a date and time."
      );

      return;
    }

    setSavingMove(true);
    setMessage("");
    setError("");

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
                `${moveDate}T${moveTime}:00`,
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

        return;
      }

      if (!response.ok) {
        throw new Error(
          data?.detail ||
            data?.error ||
            "Appointment could not be moved."
        );
      }

      setMovingAppointmentId(
        ""
      );

      setMessage(
        "Appointment moved."
      );

      await loadData();
    } catch (moveError) {
      setError(
        moveError instanceof Error
          ? moveError.message
          : "Appointment could not be moved."
      );
    } finally {
      setSavingMove(false);
    }
  }

  async function updateAppointmentStatus(
    appointmentId,
    nextStatus
  ) {
    const appointment =
      appointments.find(
        (item) =>
          item.id ===
          appointmentId
      );

    if (
      !appointment ||
      !canModifyAppointment(
        appointment
      )
    ) {
      setError(
        "You can modify only your own appointments."
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
                nextStatus,
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

        return;
      }

      if (!response.ok) {
        throw new Error(
          data?.detail ||
            data?.error ||
            "Appointment status could not be updated."
        );
      }

      setMessage(
        "Appointment updated."
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

  /*
   * BLOCKED TIME
   */

  function openBlockForm() {
    if (
      !selectedBarberId ||
      !canManageSelectedBarber
    ) {
      return;
    }

    setShowAppointmentForm(
      false
    );

    setShowBlockForm(true);

    setBlockMode(
      "one-time"
    );

    setBlockDate(
      selectedDate
    );

    setRecurringStartDate(
      selectedDate
    );

    setRecurringDays([
      weekdayValueForDate(
        selectedDate
      ),
    ]);

    setMessage("");
    setError("");
  }

  function closeBlockForm() {
    setShowBlockForm(false);
    setSavingBlock(false);
    setError("");
  }

  function handleRecurringStartDateChange(
    value
  ) {
    setRecurringStartDate(
      value
    );

    setRecurringDays([
      weekdayValueForDate(
        value
      ),
    ]);
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

  function resolvedBlockReason() {
    if (
      blockReason === "Other"
    ) {
      return (
        customBlockReason.trim() ||
        "Blocked"
      );
    }

    return blockReason;
  }

  async function saveOneTimeBlockedTime() {
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

            start_datetime:
              `${blockDate}T${blockStartTime}:00`,

            end_datetime:
              `${blockDate}T${blockEndTime}:00`,

            reason:
              resolvedBlockReason(),
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

    setMessage(
      "Blocked time created."
    );

    return true;
  }

  async function saveRecurringBlockedTime() {
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

            weekdays:
              recurringDays,

            start_date:
              recurringStartDate,

            end_date:
              recurringEndDate,

            start_time:
              blockStartTime,

            end_time:
              blockEndTime,

            reason:
              resolvedBlockReason(),
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

    setMessage(
      `Recurring blocked time created (${
        data?.occurrences_created ||
        0
      } occurrences).`
    );

    return true;
  }

  async function saveBlockedTime() {
    if (
      savingBlock ||
      !selectedBarberId
    ) {
      return;
    }

    if (
      !canManageSelectedBarber
    ) {
      setError(
        "You can block time only on your own schedule."
      );

      return;
    }

    if (
      !blockStartTime ||
      !blockEndTime
    ) {
      setError(
        "Please choose a start and end time."
      );

      return;
    }

    if (
      blockEndTime <=
      blockStartTime
    ) {
      setError(
        "End time must be after start time."
      );

      return;
    }

    if (
      blockMode ===
        "recurring" &&
      recurringDays.length === 0
    ) {
      setError(
        "Choose at least one day."
      );

      return;
    }

    if (
      blockMode ===
        "recurring" &&
      (!recurringStartDate ||
        !recurringEndDate)
    ) {
      setError(
        "Please choose the recurring start and end dates."
      );

      return;
    }

    if (
      blockMode ===
        "recurring" &&
      recurringEndDate <
        recurringStartDate
    ) {
      setError(
        "The recurring end date must be on or after the start date."
      );

      return;
    }

    setSavingBlock(true);
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
      setSavingBlock(false);
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
        "You can modify only your own blocked time."
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
      setDeletingBlockId("");
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

    const seriesBlock =
      blockedTimes.find(
        (block) =>
          block.series_id ===
          seriesId
      );

    if (
      !seriesBlock ||
      !canModifyBlockedTime(
        seriesBlock
      )
    ) {
      setError(
        "You can modify only your own blocked time."
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
      setDeletingSeriesId("");
    }
  }

  /*
   * CALENDAR DATA
   */

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

  /*
   * APPOINTMENT CARD
   */

  function appointmentCard(
    appointment
  ) {
    const isMoving =
      movingAppointmentId ===
      appointment.id;

    const canModify =
      canModifyAppointment(
        appointment
      );

    const statusStyle =
      STATUS_STYLES[
        appointment.status
      ] ||
      STATUS_STYLES.confirmed;

    const statusLabel =
      STATUS_LABELS[
        appointment.status
      ] || "Confirmed";

    return (
      <div
        key={appointment.id}
        className={`rounded-2xl p-4 border shadow-sm ${statusStyle}`}
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
                {
                  appointment.customer_name
                }
              </button>
            </p>

            <p className="text-gray-900">
              {serviceName(
                appointment.service_id
              )}
            </p>

            <p className="text-gray-900">
              {
                appointment.customer_phone
              }
            </p>

            {appointment.notes ? (
              <div className="mt-3 rounded-xl bg-white border p-3 text-gray-900">
                <p className="font-bold">
                  Notes
                </p>

                <p>
                  {
                    appointment.notes
                  }
                </p>
              </div>
            ) : null}
          </div>

          <span className="font-bold text-sm bg-white border rounded-full px-3 py-1">
            {statusLabel}
          </span>
        </div>

        {canModify &&
        !isMoving ? (
          <div className="flex flex-wrap gap-2 mt-4">
            <button
              type="button"
              onClick={() =>
                startMove(
                  appointment
                )
              }
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
        ) : null}

        {canModify &&
        isMoving ? (
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
                  setMoveDate(
                    event.target.value
                  )
                }
              />

              <input
                type="time"
                className="border rounded-xl p-3"
                value={moveTime}
                onChange={(event) =>
                  setMoveTime(
                    event.target.value
                  )
                }
              />

              <button
                type="button"
                onClick={() =>
                  saveMove(
                    appointment.id
                  )
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
        ) : null}
      </div>
    );
  }

  /*
   * BLOCKED TIME CARD
   */

  function blockedTimeCard(
    block
  ) {
    const recurring =
      Boolean(
        block.series_id
      );

    const canModify =
      canModifyBlockedTime(
        block
      );

    return (
      <div
        key={block.id}
        className="rounded-2xl p-4 bg-slate-100 border border-slate-300"
      >
        <div className="flex flex-col gap-4 sm:flex-row sm:justify-between sm:items-start">
          <div>
            <p className="font-bold">
              {formatTime(
                block.start_datetime
              )}{" "}
              –{" "}
              {formatTime(
                block.end_datetime
              )}
            </p>

            <p className="text-gray-900">
              Blocked: {block.reason}
            </p>

            {recurring ? (
              <p className="text-sm font-semibold mt-1 text-emerald-800">
                Repeats weekly
              </p>
            ) : null}
          </div>

          {canModify ? (
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
                className="bg-red-500 text-white px-3 py-2 rounded-xl text-sm font-semibold disabled:opacity-60"
              >
                {deletingBlockId ===
                block.id
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
          ) : null}
        </div>
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-emerald-50 p-4 sm:p-10">
      <div className="max-w-7xl mx-auto space-y-8">
        <AdminUserBar />

        <section className="rounded-3xl shadow-lg p-6 sm:p-8 border border-emerald-200 bg-gradient-to-r from-emerald-100 via-teal-50 to-white">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-sm font-extrabold uppercase tracking-widest text-emerald-700 mb-2">
                {displayShopName(
                  shopSlug
                )}
              </p>

              <h1 className="text-5xl font-extrabold tracking-tight mb-3">
                Calendar
              </h1>

              <p className="text-lg text-gray-700">
                View the shop schedule
                and quickly manage
                appointments and blocked
                time.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() =>
                  router.push(
                    `/${shopSlug}/admin`
                  )
                }
                className="bg-blue-600 text-white rounded-xl px-5 py-3 font-bold shadow hover:bg-blue-700"
              >
                Admin Home
              </button>

              {canManageSelectedBarber ? (
                <>
                  <button
                    type="button"
                    onClick={() =>
                      openAppointmentForm()
                    }
                    disabled={
                      !selectedBarberId
                    }
                    className="bg-blue-700 text-white rounded-xl px-5 py-3 font-bold shadow hover:bg-blue-800 disabled:opacity-50"
                  >
                    + Appointment
                  </button>

                  <button
                    type="button"
                    onClick={
                      openBlockForm
                    }
                    disabled={
                      !selectedBarberId
                    }
                    className="bg-emerald-700 text-white rounded-xl px-5 py-3 font-bold shadow hover:bg-emerald-800 disabled:opacity-50"
                  >
                    + Block Time
                  </button>
                </>
              ) : null}
            </div>
          </div>

          {message ? (
            <p className="mt-4 rounded-xl bg-green-50 border border-green-200 px-4 py-3 font-semibold text-green-700">
              {message}
            </p>
          ) : null}

          {error ? (
            <p className="mt-4 rounded-xl bg-red-50 border border-red-200 px-4 py-3 font-semibold text-red-700">
              {error}
            </p>
          ) : null}
        </section>

        {isStaff &&
        !currentUserBarberId ? (
          <section className="rounded-2xl border border-amber-300 bg-amber-50 p-4">
            <p className="font-bold text-amber-900">
              Your login is not linked
              to a staff schedule.
            </p>

            <p className="mt-1 text-amber-900">
              You can view the calendar,
              but an owner must link your
              login to a staff member
              before you can create or
              change appointments or
              blocked time.
            </p>
          </section>
        ) : null}

        {isStaff &&
        currentUserBarberId &&
        selectedBarberId &&
        !canManageSelectedBarber ? (
          <section className="rounded-2xl border border-blue-300 bg-blue-50 p-4">
            <p className="font-semibold text-blue-900">
              You can view this staff
              member&apos;s schedule.
              Only that staff member or
              the owner can make changes.
            </p>
          </section>
        ) : null}

        {showAppointmentForm &&
        canManageSelectedBarber ? (
          <section className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-blue-200">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-sm font-extrabold uppercase tracking-widest text-blue-700 mb-2">
                  New Appointment
                </p>

                <h2 className="text-3xl font-bold text-gray-950">
                  Book for{" "}
                  {selectedBarber?.name ||
                    "Staff"}
                </h2>
              </div>

              <button
                type="button"
                onClick={
                  closeAppointmentForm
                }
                disabled={
                  savingAppointment
                }
                className="self-start bg-gray-200 text-gray-900 rounded-xl px-4 py-2 font-bold disabled:opacity-60"
              >
                Close
              </button>
            </div>

            <div className="mt-6 grid gap-6 lg:grid-cols-2">
              <div>
                <label className="block text-lg font-bold mb-2">
                  Customer
                </label>

                {appointmentCustomerMode ===
                "existing" ? (
                  <div className="space-y-3">
                    <input
                      type="text"
                      autoFocus
                      value={
                        customerSearch
                      }
                      onChange={(
                        event
                      ) => {
                        setCustomerSearch(
                          event.target.value
                        );

                        setSelectedCustomerKey(
                          ""
                        );

                        setAppointmentCustomerName(
                          ""
                        );

                        setAppointmentCustomerPhone(
                          ""
                        );
                      }}
                      placeholder="Type name or phone"
                      className="w-full border-2 border-blue-200 rounded-xl p-4 text-lg"
                    />

                    {existingCustomers.length >
                    0 ? (
                      <div className="rounded-2xl border border-gray-200 overflow-hidden">
                        {filteredCustomers.length >
                        0 ? (
                          filteredCustomers.map(
                            (
                              customer
                            ) => (
                              <button
                                key={
                                  customer.key
                                }
                                type="button"
                                onClick={() =>
                                  chooseExistingCustomer(
                                    customer
                                  )
                                }
                                className={`w-full text-left px-4 py-3 border-b last:border-b-0 hover:bg-blue-50 ${
                                  selectedCustomerKey ===
                                  customer.key
                                    ? "bg-blue-100"
                                    : "bg-white"
                                }`}
                              >
                                <span className="block font-bold">
                                  {
                                    customer.name
                                  }
                                </span>

                                <span className="block text-sm text-gray-600">
                                  {
                                    customer.phone
                                  }
                                </span>
                              </button>
                            )
                          )
                        ) : (
                          <div className="p-4 text-gray-600">
                            No matching
                            customer.
                          </div>
                        )}
                      </div>
                    ) : null}

                    <button
                      type="button"
                      onClick={
                        startNewCustomer
                      }
                      className="w-full sm:w-auto bg-emerald-700 text-white rounded-xl px-5 py-3 font-bold"
                    >
                      + New Customer
                    </button>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div>
                      <label className="block font-semibold mb-2">
                        Name
                      </label>

                      <input
                        type="text"
                        autoFocus
                        value={
                          appointmentCustomerName
                        }
                        onChange={(
                          event
                        ) =>
                          setAppointmentCustomerName(
                            event.target
                              .value
                          )
                        }
                        placeholder="Customer name"
                        className="w-full border-2 border-blue-200 rounded-xl p-4 text-lg"
                      />
                    </div>

                    <div>
                      <label className="block font-semibold mb-2">
                        Phone
                      </label>

                      <input
                        type="tel"
                        value={
                          appointmentCustomerPhone
                        }
                        onChange={(
                          event
                        ) =>
                          setAppointmentCustomerPhone(
                            event.target
                              .value
                          )
                        }
                        placeholder="Customer phone"
                        className="w-full border-2 border-blue-200 rounded-xl p-4 text-lg"
                      />
                    </div>

                    {existingCustomers.length >
                    0 ? (
                      <button
                        type="button"
                        onClick={
                          useExistingCustomerMode
                        }
                        className="text-blue-700 font-bold underline"
                      >
                        Choose an existing
                        customer instead
                      </button>
                    ) : null}
                  </div>
                )}
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-lg font-bold mb-2">
                    Service
                  </label>

                  <select
                    value={
                      appointmentServiceId
                    }
                    onChange={(
                      event
                    ) =>
                      setAppointmentServiceId(
                        event.target.value
                      )
                    }
                    className="w-full border-2 border-blue-200 rounded-xl p-4 bg-white text-lg"
                  >
                    <option value="">
                      Choose service
                    </option>

                    {servicesForSelectedBarber.map(
                      (service) => (
                        <option
                          key={
                            service.id
                          }
                          value={
                            service.id
                          }
                        >
                          {
                            service.name
                          }
                          {service.duration_minutes
                            ? ` · ${service.duration_minutes} min`
                            : ""}
                        </option>
                      )
                    )}
                  </select>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="block font-bold mb-2">
                      Date
                    </label>

                    <input
                      type="date"
                      value={
                        appointmentDate
                      }
                      onChange={(
                        event
                      ) =>
                        setAppointmentDate(
                          event.target
                            .value
                        )
                      }
                      className="w-full border-2 border-blue-200 rounded-xl p-4"
                    />
                  </div>

                  <div>
                    <label className="block font-bold mb-2">
                      Time
                    </label>

                    <input
                      type="time"
                      value={
                        appointmentTime
                      }
                      onChange={(
                        event
                      ) =>
                        setAppointmentTime(
                          event.target
                            .value
                        )
                      }
                      className="w-full border-2 border-blue-200 rounded-xl p-4"
                    />
                  </div>
                </div>

                <div>
                  <label className="block font-bold mb-2">
                    Notes{" "}
                    <span className="font-normal text-gray-500">
                      (optional)
                    </span>
                  </label>

                  <textarea
                    value={
                      appointmentNotes
                    }
                    onChange={(
                      event
                    ) =>
                      setAppointmentNotes(
                        event.target.value
                      )
                    }
                    rows={3}
                    placeholder="Anything staff should know"
                    className="w-full border-2 border-blue-200 rounded-xl p-4"
                  />
                </div>
              </div>
            </div>

            <div className="flex flex-wrap gap-3 mt-7">
              <button
                type="button"
                onClick={
                  saveNewAppointment
                }
                disabled={
                  savingAppointment
                }
                className="bg-blue-700 text-white rounded-xl px-7 py-4 text-lg font-extrabold shadow hover:bg-blue-800 disabled:opacity-60"
              >
                {savingAppointment
                  ? "Booking..."
                  : "Book Appointment"}
              </button>

              <button
                type="button"
                onClick={
                  closeAppointmentForm
                }
                disabled={
                  savingAppointment
                }
                className="bg-gray-300 text-gray-900 rounded-xl px-6 py-4 font-bold disabled:opacity-60"
              >
                Cancel
              </button>
            </div>
          </section>
        ) : null}

                  {showBlockForm &&
        canManageSelectedBarber ? (
          <section className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-emerald-200">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-sm font-extrabold uppercase tracking-widest text-emerald-700 mb-2">
                  Block Time
                </p>

                <h2 className="text-3xl font-bold text-emerald-950">
                  {selectedBarber?.name ||
                    "Staff"}
                </h2>
              </div>

              <button
                type="button"
                onClick={closeBlockForm}
                disabled={savingBlock}
                className="self-start bg-gray-200 text-gray-900 rounded-xl px-4 py-2 font-bold disabled:opacity-60"
              >
                Close
              </button>
            </div>

            <div className="mt-6">
              <label className="block font-semibold mb-2">
                Type
              </label>

              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() =>
                    setBlockMode(
                      "one-time"
                    )
                  }
                  className={`rounded-xl px-4 py-3 font-bold border ${
                    blockMode ===
                    "one-time"
                      ? "bg-emerald-700 text-white border-emerald-700"
                      : "bg-white text-emerald-900 border-emerald-300"
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
                  className={`rounded-xl px-4 py-3 font-bold border ${
                    blockMode ===
                    "recurring"
                      ? "bg-emerald-700 text-white border-emerald-700"
                      : "bg-white text-emerald-900 border-emerald-300"
                  }`}
                >
                  Recurring
                </button>
              </div>
            </div>

            <div className="mt-6">
              <label className="block font-semibold mb-2">
                Reason
              </label>

              <select
                className="w-full border border-emerald-200 rounded-xl p-3 bg-emerald-50"
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

              {blockReason ===
              "Other" ? (
                <input
                  type="text"
                  className="w-full mt-3 border border-emerald-200 rounded-xl p-3 bg-emerald-50"
                  placeholder="Reason"
                  value={
                    customBlockReason
                  }
                  onChange={(event) =>
                    setCustomBlockReason(
                      event.target.value
                    )
                  }
                />
              ) : null}
            </div>

            {blockMode ===
            "one-time" ? (
              <div className="grid gap-4 sm:grid-cols-3 mt-6">
                <div>
                  <label className="block font-semibold mb-2">
                    Date
                  </label>

                  <input
                    type="date"
                    className="w-full border border-emerald-200 rounded-xl p-3 bg-emerald-50"
                    value={blockDate}
                    onChange={(event) =>
                      setBlockDate(
                        event.target.value
                      )
                    }
                  />
                </div>

                <div>
                  <label className="block font-semibold mb-2">
                    Start
                  </label>

                  <input
                    type="time"
                    className="w-full border border-emerald-200 rounded-xl p-3 bg-emerald-50"
                    value={
                      blockStartTime
                    }
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
                    className="w-full border border-emerald-200 rounded-xl p-3 bg-emerald-50"
                    value={blockEndTime}
                    onChange={(event) =>
                      setBlockEndTime(
                        event.target.value
                      )
                    }
                  />
                </div>
              </div>
            ) : (
              <div className="mt-6 space-y-5">
                <div>
                  <label className="block font-semibold mb-2">
                    Repeats On
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
                            className={`rounded-xl px-4 py-2 font-bold border ${
                              selected
                                ? "bg-emerald-700 text-white border-emerald-700"
                                : "bg-white text-emerald-900 border-emerald-300"
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

                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="block font-semibold mb-2">
                      Starts
                    </label>

                    <input
                      type="date"
                      className="w-full border border-emerald-200 rounded-xl p-3 bg-emerald-50"
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
                    />
                  </div>

                  <div>
                    <label className="block font-semibold mb-2">
                      Until
                    </label>

                    <input
                      type="date"
                      className="w-full border border-emerald-200 rounded-xl p-3 bg-emerald-50"
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
                      className="w-full border border-emerald-200 rounded-xl p-3 bg-emerald-50"
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
                    />
                  </div>

                  <div>
                    <label className="block font-semibold mb-2">
                      End
                    </label>

                    <input
                      type="time"
                      className="w-full border border-emerald-200 rounded-xl p-3 bg-emerald-50"
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
                    />
                  </div>
                </div>
              </div>
            )}

            <div className="flex flex-wrap gap-3 mt-6">
              <button
                type="button"
                onClick={
                  saveBlockedTime
                }
                disabled={
                  savingBlock
                }
                className="bg-emerald-700 text-white rounded-xl px-5 py-3 font-bold disabled:opacity-60"
              >
                {savingBlock
                  ? "Saving..."
                  : blockMode ===
                      "recurring"
                    ? "Save Recurring Block"
                    : "Save Blocked Time"}
              </button>

              <button
                type="button"
                onClick={
                  closeBlockForm
                }
                disabled={
                  savingBlock
                }
                className="bg-gray-400 text-white rounded-xl px-5 py-3 font-bold disabled:opacity-60"
              >
                Cancel
              </button>
            </div>
          </section>
        ) : null}

        <section className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-emerald-200">
          <h2 className="text-3xl font-bold mb-6 text-emerald-950">
            Filters
          </h2>

          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <label className="block font-semibold mb-2">
                View
              </label>

              <select
                className="w-full border border-emerald-200 rounded-xl p-3 bg-emerald-50"
                value={viewMode}
                onChange={(event) =>
                  setViewMode(
                    event.target.value
                  )
                }
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
              <label className="block font-semibold mb-2">
                Date
              </label>

              <input
                type="date"
                className="w-full border border-emerald-200 rounded-xl p-3 bg-emerald-50"
                value={selectedDate}
                onChange={(event) => {
                  setSelectedDate(
                    event.target.value
                  );

                  setShowAppointmentForm(
                    false
                  );

                  setShowBlockForm(
                    false
                  );

                  setMovingAppointmentId(
                    ""
                  );
                }}
              />
            </div>

            <div>
              <label className="block font-semibold mb-2">
                Staff
              </label>

              <select
                className="w-full border border-emerald-200 rounded-xl p-3 bg-emerald-50"
                value={
                  selectedBarberId
                }
                onChange={(event) => {
                  setSelectedBarberId(
                    event.target.value
                  );

                  setShowAppointmentForm(
                    false
                  );

                  setShowBlockForm(
                    false
                  );

                  setMovingAppointmentId(
                    ""
                  );
                }}
              >
                {barbers.map(
                  (barber) => (
                    <option
                      key={barber.id}
                      value={barber.id}
                    >
                      {barber.name}
                    </option>
                  )
                )}
              </select>
            </div>
          </div>
        </section>

        {loading ? (
          <section className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-emerald-200">
            <p className="text-2xl font-bold">
              Loading calendar...
            </p>
          </section>
        ) : null}

        {!loading &&
        viewMode === "day" ? (
          <section className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-emerald-200">
            <h2 className="text-3xl font-bold mb-2 text-emerald-950">
              Day View —{" "}
              {selectedBarber?.name ||
                "Staff"}{" "}
              — {selectedDate}
            </h2>

            {canManageSelectedBarber ? (
              <p className="text-gray-600 mb-6">
                Click{" "}
                <strong>
                  + Appointment
                </strong>{" "}
                on an open hour to book
                that time immediately.
              </p>
            ) : (
              <div className="mb-6" />
            )}

            <div className="grid gap-3">
              {HOURS.map(
                (hour) => {
                  const appointmentsForHour =
                    appointmentItemsForHour(
                      hour
                    );

                  const blockedForHour =
                    blockedItemsForHour(
                      hour
                    );

                  const isOpen =
                    appointmentsForHour.length ===
                      0 &&
                    blockedForHour.length ===
                      0;

                  return (
                    <div
                      key={hour}
                      className="border border-emerald-100 rounded-2xl p-4 bg-emerald-50/50"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
                        <p className="font-bold text-emerald-950">
                          {hour}
                        </p>

                        {isOpen &&
                        canManageSelectedBarber ? (
                          <button
                            type="button"
                            onClick={() =>
                              openAppointmentForm(
                                hour
                              )
                            }
                            className="bg-blue-600 text-white rounded-lg px-3 py-2 text-sm font-bold hover:bg-blue-700"
                          >
                            + Appointment
                          </button>
                        ) : null}
                      </div>

                      {isOpen ? (
                        <p className="text-gray-600">
                          Open
                        </p>
                      ) : null}

                      <div className="grid gap-2">
                        {appointmentsForHour.map(
                          (
                            appointment
                          ) =>
                            appointmentCard(
                              appointment
                            )
                        )}

                        {blockedForHour.map(
                          (block) =>
                            blockedTimeCard(
                              block
                            )
                        )}
                      </div>
                    </div>
                  );
                }
              )}
            </div>
          </section>
        ) : null}

        {!loading &&
        viewMode === "week" ? (
          <section className="bg-white rounded-3xl shadow-lg p-6 sm:p-8 border border-emerald-200">
            <h2 className="text-3xl font-bold mb-6 text-emerald-950">
              Week View —{" "}
              {selectedBarber?.name ||
                "Staff"}
            </h2>

            <div className="grid gap-4">
              {weekDates.map(
                (
                  date,
                  index
                ) => {
                  const items =
                    weekItemsForDate(
                      date
                    );

                  return (
                    <div
                      key={date}
                      className="border border-emerald-100 rounded-2xl p-4 bg-emerald-50/50"
                    >
                      <div className="flex flex-wrap justify-between items-center gap-3 mb-3">
                        <h3 className="text-xl font-bold text-emerald-950">
                          {DAYS[index]} —{" "}
                          {date}
                        </h3>

                        {canManageSelectedBarber ? (
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedDate(
                                date
                              );

                              setViewMode(
                                "day"
                              );

                              setAppointmentDate(
                                date
                              );

                              openAppointmentForm();
                            }}
                            className="bg-blue-600 text-white rounded-lg px-3 py-2 text-sm font-bold hover:bg-blue-700"
                          >
                            + Appointment
                          </button>
                        ) : null}
                      </div>

                      {items.length ===
                      0 ? (
                        <p className="text-gray-600">
                          No appointments
                          or blocked time.
                        </p>
                      ) : null}

                      <div className="grid gap-2">
                        {items.map(
                          (item) =>
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
                }
              )}
            </div>
          </section>
        ) : null}
      </div>
    </main>
  );
}
