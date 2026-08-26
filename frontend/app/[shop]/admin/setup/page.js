"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

const API_BASE = "https://chairtime-production-94da.up.railway.app";

const WEEKDAY_NAMES = {
  0: "Monday",
  1: "Tuesday",
  2: "Wednesday",
  3: "Thursday",
  4: "Friday",
  5: "Saturday",
  6: "Sunday",
};

const WEEKDAY_MAP = {
  Monday: 0,
  Tuesday: 1,
  Wednesday: 2,
  Thursday: 3,
  Friday: 4,
  Saturday: 5,
  Sunday: 6,
};

const WEEKDAYS = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

export default function SetupPage() {
  const params = useParams();
  const shopSlug = params.shop;

  const [barbers, setBarbers] = useState([]);
  const [services, setServices] = useState([]);
  const [serviceCatalog, setServiceCatalog] = useState([]);
  const [blockedTimes, setBlockedTimes] = useState([]);
  const [availabilityRules, setAvailabilityRules] = useState([]);

  const [shopAvailabilityRules, setShopAvailabilityRules] =
    useState([]);
  const [shopBlockedTimes, setShopBlockedTimes] = useState([]);

  const [selectedBarberId, setSelectedBarberId] = useState("");

  const [serviceName, setServiceName] = useState("");
  const [serviceDuration, setServiceDuration] = useState("30");
  const [servicePrice, setServicePrice] = useState("");

  const [editingServiceId, setEditingServiceId] = useState("");
  const [editedServiceName, setEditedServiceName] = useState("");
  const [editedServiceDuration, setEditedServiceDuration] =
    useState("");
  const [editedServicePrice, setEditedServicePrice] = useState("");

  const [availabilityDay, setAvailabilityDay] = useState("Monday");
  const [availabilityStart, setAvailabilityStart] = useState("09:00");
  const [availabilityEnd, setAvailabilityEnd] = useState("17:00");

  const [blockReason, setBlockReason] = useState("Lunch");
  const [blockStart, setBlockStart] = useState("");
  const [blockEnd, setBlockEnd] = useState("");

  const [fullDayDate, setFullDayDate] = useState(
    new Date().toISOString().slice(0, 10)
  );

  /*
   * Shop-wide hours
   */
  const [shopHoursDay, setShopHoursDay] = useState("Monday");
  const [shopHoursStart, setShopHoursStart] = useState("09:00");
  const [shopHoursEnd, setShopHoursEnd] = useState("17:00");

  /*
   * One-time shop-wide time block
   */
  const [shopBlockReason, setShopBlockReason] = useState("Closed");
  const [shopBlockStart, setShopBlockStart] = useState("");
  const [shopBlockEnd, setShopBlockEnd] = useState("");

  /*
   * One-time full-day shop closure
   */
  const [shopClosureDate, setShopClosureDate] = useState(
    new Date().toISOString().slice(0, 10)
  );

  const [shopClosureReason, setShopClosureReason] =
    useState("Closed");

  /*
   * Recurring shop-wide block
   */
  const [recurringReason, setRecurringReason] = useState("Lunch");

  const [recurringStartDate, setRecurringStartDate] = useState(
    new Date().toISOString().slice(0, 10)
  );

  const [recurringEndDate, setRecurringEndDate] = useState(
    new Date().toISOString().slice(0, 10)
  );

  const [recurringStartTime, setRecurringStartTime] =
    useState("12:00");

  const [recurringEndTime, setRecurringEndTime] =
    useState("13:00");

  const [recurringWeekdays, setRecurringWeekdays] = useState([
    0,
    1,
    2,
    3,
    4,
  ]);

  const [message, setMessage] = useState("");

  async function loadData() {
    if (!shopSlug) return;

    const query =
      "?shop_slug=" + encodeURIComponent(shopSlug);

    try {
      const [
        barbersRes,
        servicesRes,
        catalogRes,
        blockedRes,
        availabilityRes,
        shopAvailabilityRes,
        shopBlockedRes,
      ] = await Promise.all([
        fetch(`${API_BASE}/api/barbers${query}`),
        fetch(`${API_BASE}/api/services${query}`),
        fetch(`${API_BASE}/api/service-catalog${query}`),
        fetch(`${API_BASE}/api/blocked-times${query}`),
        fetch(`${API_BASE}/api/availability-rules${query}`),
        fetch(`${API_BASE}/api/shop-availability-rules${query}`),
        fetch(`${API_BASE}/api/shop-blocked-times${query}`),
      ]);

      if (
        !barbersRes.ok ||
        !servicesRes.ok ||
        !catalogRes.ok ||
        !blockedRes.ok ||
        !availabilityRes.ok ||
        !shopAvailabilityRes.ok ||
        !shopBlockedRes.ok
      ) {
        setMessage("Could not load shop setup.");
        return;
      }

      const barbersData = await barbersRes.json();
      const servicesData = await servicesRes.json();
      const catalogData = await catalogRes.json();
      const blockedData = await blockedRes.json();
      const availabilityData =
        await availabilityRes.json();

      const shopAvailabilityData =
        await shopAvailabilityRes.json();

      const shopBlockedData =
        await shopBlockedRes.json();

      setBarbers(barbersData);
      setServices(servicesData);
      setServiceCatalog(catalogData);
      setBlockedTimes(blockedData);
      setAvailabilityRules(availabilityData);
      setShopAvailabilityRules(shopAvailabilityData);
      setShopBlockedTimes(shopBlockedData);

      if (barbersData.length > 0) {
        setSelectedBarberId((current) => {
          const stillExists = barbersData.some(
            (barber) => barber.id === current
          );

          if (current && stillExists) {
            return current;
          }

          return barbersData[0].id;
        });
      } else {
        setSelectedBarberId("");
      }
    } catch (error) {
      console.error(error);
      setMessage("Could not load shop setup.");
    }
  }

  useEffect(() => {
    if (shopSlug) {
      loadData();
    }
  }, [shopSlug]);

  function formatTime(value) {
    if (!value) return "";
    return String(value).slice(0, 5);
  }

  function formatDateTime(value) {
    if (!value) return "";

    return new Date(value).toLocaleString();
  }

  function formatDate(value) {
    if (!value) return "";

    const datePart = String(value).slice(0, 10);
    const [year, month, day] = datePart.split("-");

    if (!year || !month || !day) {
      return new Date(value).toLocaleDateString();
    }

    return new Date(
      Number(year),
      Number(month) - 1,
      Number(day)
    ).toLocaleDateString();
  }

  function isFullDay(block) {
    return (
      block.start_datetime?.endsWith("T00:00:00") &&
      block.end_datetime?.endsWith("T23:59:00")
    );
  }

  function getErrorMessage(error, fallback) {
    if (!error) return fallback;

    if (typeof error.detail === "string") {
      return error.detail;
    }

    if (
      error.detail &&
      typeof error.detail === "object" &&
      typeof error.detail.message === "string"
    ) {
      return error.detail.message;
    }

    return fallback;
  }

  function handleBarberChange(barberId) {
    setSelectedBarberId(barberId);

    setServiceName("");
    setServiceDuration("30");
    setServicePrice("");

    cancelEditingService();

    setAvailabilityDay("Monday");
    setAvailabilityStart("09:00");
    setAvailabilityEnd("17:00");

    setBlockReason("Lunch");
    setBlockStart("");
    setBlockEnd("");

    setMessage("");
  }

  /*
   * SHOP-WIDE HOURS
   */

  async function addShopHours() {
    if (!shopHoursStart || !shopHoursEnd) {
      setMessage("Enter shop opening and closing times.");
      return;
    }

    if (shopHoursStart >= shopHoursEnd) {
      setMessage(
        "Shop closing time must be later than opening time."
      );
      return;
    }

    const response = await fetch(
      `${API_BASE}/api/shop-availability-rules`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          shop_slug: shopSlug,
          weekday: WEEKDAY_MAP[shopHoursDay],
          start_time: `${shopHoursStart}:00`,
          end_time: `${shopHoursEnd}:00`,
        }),
      }
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({}));

      setMessage(
        getErrorMessage(
          error,
          "Could not save shop hours."
        )
      );

      return;
    }

    setMessage(`${shopHoursDay} shop hours saved.`);
    loadData();
  }

  async function deleteShopHours(ruleId) {
    const response = await fetch(
      `${API_BASE}/api/shop-availability-rules/${encodeURIComponent(
        ruleId
      )}`,
      {
        method: "DELETE",
      }
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({}));

      setMessage(
        getErrorMessage(
          error,
          "Could not delete shop hours."
        )
      );

      return;
    }

    setMessage("Shop hours removed.");
    loadData();
  }

  async function closeShopWeekday(weekday) {
    const rulesForDay = shopAvailabilityRules.filter(
      (rule) => rule.weekday === weekday
    );

    if (rulesForDay.length === 0) {
      setMessage(
        `${WEEKDAY_NAMES[weekday]} is already closed.`
      );
      return;
    }

    const confirmed = window.confirm(
      `Mark the shop closed every ${WEEKDAY_NAMES[weekday]}?`
    );

    if (!confirmed) return;

    for (const rule of rulesForDay) {
      const response = await fetch(
        `${API_BASE}/api/shop-availability-rules/${encodeURIComponent(
          rule.id
        )}`,
        {
          method: "DELETE",
        }
      );

      if (!response.ok) {
        setMessage(
          `Could not mark ${WEEKDAY_NAMES[weekday]} closed.`
        );
        return;
      }
    }

    setMessage(
      `Shop is now closed on ${WEEKDAY_NAMES[weekday]}s.`
    );

    loadData();
  }

  /*
   * SHOP-WIDE ONE-TIME BLOCK
   */

  async function addShopBlockTime() {
    if (!shopBlockStart || !shopBlockEnd) {
      setMessage(
        "Enter the start and end of the shop-wide block."
      );
      return;
    }

    if (shopBlockStart >= shopBlockEnd) {
      setMessage(
        "Shop block end time must be later than start time."
      );
      return;
    }

    const response = await fetch(
      `${API_BASE}/api/shop-blocked-times`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          shop_slug: shopSlug,
          reason:
            shopBlockReason.trim() || "Closed",
          start_datetime: shopBlockStart,
          end_datetime: shopBlockEnd,
        }),
      }
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({}));

      setMessage(
        getErrorMessage(
          error,
          "Could not block the shop."
        )
      );

      return;
    }

    setShopBlockReason("Closed");
    setShopBlockStart("");
    setShopBlockEnd("");

    setMessage("Shop-wide time blocked.");
    loadData();
  }

  /*
   * SHOP-WIDE FULL DAY
   */

  async function addShopFullDayClosure(
    reason = shopClosureReason
  ) {
    if (!shopClosureDate) {
      setMessage("Choose a closure date.");
      return;
    }

    const cleanReason =
      String(reason || "").trim() || "Closed";

    const response = await fetch(
      `${API_BASE}/api/shop-blocked-times`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          shop_slug: shopSlug,
          reason: cleanReason,
          start_datetime:
            `${shopClosureDate}T00:00:00`,
          end_datetime:
            `${shopClosureDate}T23:59:00`,
        }),
      }
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({}));

      setMessage(
        getErrorMessage(
          error,
          "Could not close the shop."
        )
      );

      return;
    }

    setMessage(
      `${cleanReason} shop closure saved.`
    );

    loadData();
  }

  /*
   * SHOP-WIDE RECURRING BLOCK
   */

  function toggleRecurringWeekday(weekday) {
    setRecurringWeekdays((current) => {
      if (current.includes(weekday)) {
        return current.filter(
          (item) => item !== weekday
        );
      }

      return [...current, weekday].sort(
        (a, b) => a - b
      );
    });
  }

  async function addRecurringShopBlock() {
    if (!recurringReason.trim()) {
      setMessage(
        "Enter a reason for the recurring block."
      );
      return;
    }

    if (
      !recurringStartDate ||
      !recurringEndDate
    ) {
      setMessage(
        "Choose the recurring block start and end dates."
      );
      return;
    }

    if (recurringEndDate < recurringStartDate) {
      setMessage(
        "Recurring end date must be on or after start date."
      );
      return;
    }

    if (
      !recurringStartTime ||
      !recurringEndTime
    ) {
      setMessage(
        "Enter recurring start and end times."
      );
      return;
    }

    if (
      recurringStartTime >= recurringEndTime
    ) {
      setMessage(
        "Recurring end time must be later than start time."
      );
      return;
    }

    if (recurringWeekdays.length === 0) {
      setMessage(
        "Choose at least one weekday."
      );
      return;
    }

    const response = await fetch(
      `${API_BASE}/api/shop-blocked-times/recurring`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          shop_slug: shopSlug,
          reason: recurringReason.trim(),
          start_date: recurringStartDate,
          end_date: recurringEndDate,
          start_time: `${recurringStartTime}:00`,
          end_time: `${recurringEndTime}:00`,
          weekdays: recurringWeekdays,
        }),
      }
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({}));

      setMessage(
        getErrorMessage(
          error,
          "Could not create recurring shop block."
        )
      );

      return;
    }

    const data = await response.json();

    setMessage(
      `Recurring shop block created${
        data.occurrences_created
          ? ` (${data.occurrences_created} occurrences).`
          : "."
      }`
    );

    loadData();
  }

  async function deleteShopBlockedTime(block) {
    const confirmed = window.confirm(
      `Delete this ${block.reason} shop block?`
    );

    if (!confirmed) return;

    const response = await fetch(
      `${API_BASE}/api/shop-blocked-times/${encodeURIComponent(
        block.id
      )}`,
      {
        method: "DELETE",
      }
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({}));

      setMessage(
        getErrorMessage(
          error,
          "Could not delete shop block."
        )
      );

      return;
    }

    setMessage("Shop block deleted.");
    loadData();
  }

  async function deleteShopBlockedSeries(block) {
    if (!block.series_id) return;

    const confirmed = window.confirm(
      `Delete the entire recurring ${block.reason} series?`
    );

    if (!confirmed) return;

    const response = await fetch(
      `${API_BASE}/api/shop-blocked-time-series/${encodeURIComponent(
        block.series_id
      )}?shop_slug=${encodeURIComponent(shopSlug)}`,
      {
        method: "DELETE",
      }
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({}));

      setMessage(
        getErrorMessage(
          error,
          "Could not delete recurring shop block."
        )
      );

      return;
    }

    setMessage(
      "Recurring shop block series deleted."
    );

    loadData();
  }

  /*
   * STAFF SERVICES
   */

  async function addService() {
    const duration = Number(serviceDuration);
    const price = Number(servicePrice);

    if (!selectedBarberId) {
      setMessage("Choose a staff member.");
      return;
    }

    if (!serviceName) {
      setMessage("Choose a service.");
      return;
    }

    if (!duration || duration <= 0) {
      setMessage("Enter a valid duration.");
      return;
    }

    if (
      servicePrice === "" ||
      Number.isNaN(price) ||
      price < 0
    ) {
      setMessage("Enter a valid price.");
      return;
    }

    const response = await fetch(
      `${API_BASE}/api/services`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          shop_slug: shopSlug,
          barber_id: selectedBarberId,
          name: serviceName,
          duration_minutes: duration,
          price,
        }),
      }
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({}));

      setMessage(
        getErrorMessage(
          error,
          "Could not assign service."
        )
      );

      return;
    }

    setServiceName("");
    setServiceDuration("30");
    setServicePrice("");

    setMessage("Service assigned.");

    loadData();
  }

  function startEditingService(service) {
    setEditingServiceId(service.id);
    setEditedServiceName(service.name);

    setEditedServiceDuration(
      String(service.duration_minutes)
    );

    setEditedServicePrice(
      String(service.price)
    );

    setMessage("");
  }

  function cancelEditingService() {
    setEditingServiceId("");
    setEditedServiceName("");
    setEditedServiceDuration("");
    setEditedServicePrice("");
  }

  async function updateService(serviceId) {
    const duration = Number(
      editedServiceDuration
    );

    const price = Number(
      editedServicePrice
    );

    if (!editedServiceName) {
      setMessage("Choose a service.");
      return;
    }

    if (!duration || duration <= 0) {
      setMessage("Enter a valid duration.");
      return;
    }

    if (
      editedServicePrice === "" ||
      Number.isNaN(price) ||
      price < 0
    ) {
      setMessage("Enter a valid price.");
      return;
    }

    const response = await fetch(
      `${API_BASE}/api/services/${encodeURIComponent(
        serviceId
      )}`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: editedServiceName,
          duration_minutes: duration,
          price,
        }),
      }
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({}));

      setMessage(
        getErrorMessage(
          error,
          "Could not update service."
        )
      );

      return;
    }

    cancelEditingService();

    setMessage("Service updated.");

    loadData();
  }

  async function deleteService(service) {
    const confirmed = window.confirm(
      `Remove ${service.name} from this staff member?`
    );

    if (!confirmed) return;

    const response = await fetch(
      `${API_BASE}/api/services/${encodeURIComponent(
        service.id
      )}`,
      {
        method: "DELETE",
      }
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({}));

      setMessage(
        getErrorMessage(
          error,
          "Could not remove service."
        )
      );

      return;
    }

    setMessage(
      "Service removed from staff member."
    );

    loadData();
  }

  /*
   * STAFF AVAILABILITY
   */

  async function addAvailabilityRule() {
    if (!selectedBarberId) {
      setMessage("Choose a staff member.");
      return;
    }

    if (
      !availabilityStart ||
      !availabilityEnd
    ) {
      setMessage(
        "Enter start and end times."
      );

      return;
    }

    if (
      availabilityStart >= availabilityEnd
    ) {
      setMessage(
        "End time must be later than start time."
      );

      return;
    }

    const response = await fetch(
      `${API_BASE}/api/availability-rules`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          shop_slug: shopSlug,
          barber_id: selectedBarberId,
          weekday:
            WEEKDAY_MAP[availabilityDay],
          start_time: `${availabilityStart}:00`,
          end_time: `${availabilityEnd}:00`,
        }),
      }
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({}));

      setMessage(
        getErrorMessage(
          error,
          "Could not save availability."
        )
      );

      return;
    }

    setMessage(
      "Weekly availability saved."
    );

    loadData();
  }

  async function deleteAvailabilityRule(id) {
    const response = await fetch(
      `${API_BASE}/api/availability-rules/${encodeURIComponent(
        id
      )}`,
      {
        method: "DELETE",
      }
    );

    if (!response.ok) {
      setMessage(
        "Could not delete availability."
      );

      return;
    }

    setMessage(
      "Weekly availability deleted."
    );

    loadData();
  }

  /*
   * STAFF BLOCKS
   */

  async function blockTime() {
    if (!selectedBarberId) {
      setMessage("Choose a staff member.");
      return;
    }

    if (!blockStart || !blockEnd) {
      setMessage(
        "Enter the start and end of the blocked time."
      );

      return;
    }

    if (blockStart >= blockEnd) {
      setMessage(
        "End time must be later than start time."
      );

      return;
    }

    const response = await fetch(
      `${API_BASE}/api/blocked-times`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          shop_slug: shopSlug,
          barber_id: selectedBarberId,
          reason:
            blockReason.trim() || "Blocked",
          start_datetime: blockStart,
          end_datetime: blockEnd,
        }),
      }
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({}));

      setMessage(
        getErrorMessage(
          error,
          "Could not block time."
        )
      );

      return;
    }

    setBlockReason("Lunch");
    setBlockStart("");
    setBlockEnd("");

    setMessage("Time blocked.");

    loadData();
  }

  async function blockFullDay(reason) {
    if (!selectedBarberId || !fullDayDate) {
      setMessage(
        "Choose a staff member and date."
      );

      return;
    }

    const response = await fetch(
      `${API_BASE}/api/blocked-times`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          shop_slug: shopSlug,
          barber_id: selectedBarberId,
          reason,
          start_datetime:
            `${fullDayDate}T00:00:00`,
          end_datetime:
            `${fullDayDate}T23:59:00`,
        }),
      }
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({}));

      setMessage(
        getErrorMessage(
          error,
          "Could not block full day."
        )
      );

      return;
    }

    setMessage(
      `${reason} full day blocked.`
    );

    loadData();
  }

  async function deleteBlockedTime(id) {
    const response = await fetch(
      `${API_BASE}/api/blocked-times/${encodeURIComponent(
        id
      )}`,
      {
        method: "DELETE",
      }
    );

    if (!response.ok) {
      setMessage(
        "Could not remove blocked time."
      );

      return;
    }

    setMessage(
      "Blocked time removed."
    );

    loadData();
  }

  /*
   * DERIVED DATA
   */

  const selectedBarber = useMemo(() => {
    return (
      barbers.find(
        (barber) =>
          barber.id === selectedBarberId
      ) || null
    );
  }, [barbers, selectedBarberId]);

  const selectedBarberServices =
    useMemo(() => {
      return services
        .filter(
          (service) =>
            service.barber_id ===
            selectedBarberId
        )
        .sort((a, b) =>
          String(a.name).localeCompare(
            String(b.name)
          )
        );
    }, [
      services,
      selectedBarberId,
    ]);

  const availableCatalogServices =
    useMemo(() => {
      const assignedNames = new Set(
        selectedBarberServices.map(
          (service) =>
            String(service.name)
              .trim()
              .toLowerCase()
        )
      );

      return serviceCatalog
        .filter(
          (service) =>
            !assignedNames.has(
              String(service.name)
                .trim()
                .toLowerCase()
            )
        )
        .sort((a, b) =>
          String(a.name).localeCompare(
            String(b.name)
          )
        );
    }, [
      serviceCatalog,
      selectedBarberServices,
    ]);

  const selectedBarberAvailability =
    useMemo(() => {
      return availabilityRules
        .filter(
          (rule) =>
            rule.barber_id ===
            selectedBarberId
        )
        .sort((a, b) => {
          if (
            a.weekday !== b.weekday
          ) {
            return (
              a.weekday -
              b.weekday
            );
          }

          return String(
            a.start_time
          ).localeCompare(
            String(b.start_time)
          );
        });
    }, [
      availabilityRules,
      selectedBarberId,
    ]);

  const selectedBarberBlockedTimes =
    useMemo(() => {
      const now = new Date();

      return blockedTimes
        .filter(
          (block) =>
            block.barber_id ===
              selectedBarberId &&
            new Date(
              block.end_datetime
            ) >= now
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
    ]);

  const sortedShopHours = useMemo(() => {
    return [...shopAvailabilityRules].sort(
      (a, b) => {
        if (a.weekday !== b.weekday) {
          return a.weekday - b.weekday;
        }

        return String(
          a.start_time
        ).localeCompare(
          String(b.start_time)
        );
      }
    );
  }, [shopAvailabilityRules]);

  const groupedShopHours = useMemo(() => {
    const grouped = {};

    for (
      let weekday = 0;
      weekday <= 6;
      weekday++
    ) {
      grouped[weekday] = [];
    }

    for (const rule of sortedShopHours) {
      grouped[rule.weekday].push(rule);
    }

    return grouped;
  }, [sortedShopHours]);

  const upcomingShopBlockedTimes =
    useMemo(() => {
      const now = new Date();

      return [...shopBlockedTimes]
        .filter(
          (block) =>
            new Date(
              block.end_datetime
            ) >= now
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
    }, [shopBlockedTimes]);

  return (
    <main className="min-h-screen bg-indigo-50 p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        <section className="rounded-3xl shadow-lg p-6 border border-indigo-200 bg-gradient-to-r from-indigo-100 via-violet-50 to-white">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-sm font-extrabold uppercase tracking-widest text-indigo-700 mb-2">
                {shopSlug}
              </p>

              <h1 className="text-5xl font-extrabold tracking-tight text-gray-950">
                Shop Setup
              </h1>

              <p className="mt-2 text-lg text-gray-700">
                Manage shop hours, closures, staff schedules, and services.
              </p>
            </div>

            <a
              href={`/${shopSlug}/admin`}
              className="inline-flex items-center justify-center bg-blue-600 text-white px-5 py-3 rounded-xl font-bold shadow hover:bg-blue-700"
            >
              Admin Home
            </a>
          </div>
        </section>

        {message && (
          <div className="bg-green-100 p-3 rounded-xl font-bold">
            {message}
          </div>
        )}

        {/* SHOP-WIDE SETTINGS */}

        <div className="bg-white p-6 rounded-2xl shadow-lg border border-indigo-200 space-y-5">
          <div>
            <h2 className="text-2xl font-bold">
              Shop Hours
            </h2>

            <p className="text-gray-600 mt-1">
              These hours apply to the entire shop.
              A day with no hours is closed.
            </p>
          </div>

          <select
            value={shopHoursDay}
            onChange={(event) =>
              setShopHoursDay(
                event.target.value
              )
            }
            className="border p-3 rounded w-full"
          >
            {WEEKDAYS.map((day) => (
              <option
                key={day}
                value={day}
              >
                {day}
              </option>
            ))}
          </select>

          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <p className="font-bold mb-1">
                Opens
              </p>

              <input
                type="time"
                value={shopHoursStart}
                onChange={(event) =>
                  setShopHoursStart(
                    event.target.value
                  )
                }
                className="border p-3 rounded w-full"
              />
            </div>

            <div>
              <p className="font-bold mb-1">
                Closes
              </p>

              <input
                type="time"
                value={shopHoursEnd}
                onChange={(event) =>
                  setShopHoursEnd(
                    event.target.value
                  )
                }
                className="border p-3 rounded w-full"
              />
            </div>
          </div>

          <button
            onClick={addShopHours}
            className="bg-black text-white px-4 py-3 rounded-xl font-bold"
          >
            Save Shop Hours
          </button>

          <div className="space-y-2">
            {WEEKDAYS.map((dayName) => {
              const weekday =
                WEEKDAY_MAP[dayName];

              const rules =
                groupedShopHours[
                  weekday
                ] || [];

              return (
                <div
                  key={dayName}
                  className="border rounded-xl p-3"
                >
                  <div className="flex justify-between items-center gap-3">
                    <div>
                      <p className="font-bold">
                        {dayName}
                      </p>

                      {rules.length === 0 ? (
                        <p className="text-sm text-gray-500">
                          Closed
                        </p>
                      ) : (
                        rules.map((rule) => (
                          <div
                            key={rule.id}
                            className="text-sm text-gray-700 mt-1"
                          >
                            {formatTime(
                              rule.start_time
                            )}{" "}
                            -{" "}
                            {formatTime(
                              rule.end_time
                            )}
                          </div>
                        ))
                      )}
                    </div>

                    <div className="flex flex-wrap gap-2 justify-end">
                      {rules.map((rule) => (
                        <button
                          key={rule.id}
                          onClick={() =>
                            deleteShopHours(
                              rule.id
                            )
                          }
                          className="bg-red-500 text-white px-3 py-1 rounded"
                        >
                          Delete Hours
                        </button>
                      ))}

                      {rules.length > 0 && (
                        <button
                          onClick={() =>
                            closeShopWeekday(
                              weekday
                            )
                          }
                          className="bg-gray-200 px-3 py-1 rounded"
                        >
                          Closed
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="bg-white p-6 rounded-2xl shadow-lg border border-indigo-200 space-y-5">
          <div>
            <h2 className="text-2xl font-bold">
              Shop Closures & Breaks
            </h2>

            <p className="text-gray-600 mt-1">
              These blocks apply to every staff
              member in the shop.
            </p>
          </div>

          <div className="border rounded-2xl p-4 space-y-3">
            <h3 className="text-xl font-bold">
              One-Time Time Block
            </h3>

            <p className="text-sm text-gray-600">
              Use this for a staff meeting,
              special closure, or another
              one-time period when nobody can
              be booked.
            </p>

            <input
              type="text"
              value={shopBlockReason}
              onChange={(event) =>
                setShopBlockReason(
                  event.target.value
                )
              }
              placeholder="Reason"
              className="border p-3 rounded w-full"
            />

            <input
              type="datetime-local"
              value={shopBlockStart}
              onChange={(event) =>
                setShopBlockStart(
                  event.target.value
                )
              }
              className="border p-3 rounded w-full"
            />

            <input
              type="datetime-local"
              value={shopBlockEnd}
              onChange={(event) =>
                setShopBlockEnd(
                  event.target.value
                )
              }
              className="border p-3 rounded w-full"
            />

            <button
              onClick={addShopBlockTime}
              className="bg-black text-white px-4 py-3 rounded-xl font-bold"
            >
              Block Entire Shop
            </button>
          </div>

          <div className="border rounded-2xl p-4 space-y-3">
            <h3 className="text-xl font-bold">
              Full-Day Shop Closure
            </h3>

            <p className="text-sm text-gray-600">
              Use this for a holiday, vacation
              day, weather closure, or other
              full-day closing.
            </p>

            <input
              type="date"
              value={shopClosureDate}
              onChange={(event) =>
                setShopClosureDate(
                  event.target.value
                )
              }
              className="border p-3 rounded w-full"
            />

            <input
              type="text"
              value={shopClosureReason}
              onChange={(event) =>
                setShopClosureReason(
                  event.target.value
                )
              }
              placeholder="Reason"
              className="border p-3 rounded w-full"
            />

            <div className="flex flex-wrap gap-3">
              <button
                onClick={() =>
                  addShopFullDayClosure(
                    shopClosureReason
                  )
                }
                className="bg-black text-white px-4 py-3 rounded-xl font-bold"
              >
                Close Shop
              </button>

              <button
                onClick={() =>
                  addShopFullDayClosure(
                    "Vacation"
                  )
                }
                className="bg-gray-800 text-white px-4 py-3 rounded-xl font-bold"
              >
                Vacation
              </button>

              <button
                onClick={() =>
                  addShopFullDayClosure(
                    "Holiday"
                  )
                }
                className="bg-gray-200 px-4 py-3 rounded-xl font-bold"
              >
                Holiday
              </button>
            </div>
          </div>

          <div className="border rounded-2xl p-4 space-y-3">
            <h3 className="text-xl font-bold">
              Recurring Shop Block
            </h3>

            <p className="text-sm text-gray-600">
              Use this for a recurring lunch,
              staff meeting, or another
              shop-wide break.
            </p>

            <input
              type="text"
              value={recurringReason}
              onChange={(event) =>
                setRecurringReason(
                  event.target.value
                )
              }
              placeholder="Reason"
              className="border p-3 rounded w-full"
            />

            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <p className="font-bold mb-1">
                  Start Date
                </p>

                <input
                  type="date"
                  value={recurringStartDate}
                  onChange={(event) =>
                    setRecurringStartDate(
                      event.target.value
                    )
                  }
                  className="border p-3 rounded w-full"
                />
              </div>

              <div>
                <p className="font-bold mb-1">
                  End Date
                </p>

                <input
                  type="date"
                  value={recurringEndDate}
                  onChange={(event) =>
                    setRecurringEndDate(
                      event.target.value
                    )
                  }
                  className="border p-3 rounded w-full"
                />
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <p className="font-bold mb-1">
                  Start Time
                </p>

                <input
                  type="time"
                  value={recurringStartTime}
                  onChange={(event) =>
                    setRecurringStartTime(
                      event.target.value
                    )
                  }
                  className="border p-3 rounded w-full"
                />
              </div>

              <div>
                <p className="font-bold mb-1">
                  End Time
                </p>

                <input
                  type="time"
                  value={recurringEndTime}
                  onChange={(event) =>
                    setRecurringEndTime(
                      event.target.value
                    )
                  }
                  className="border p-3 rounded w-full"
                />
              </div>
            </div>

            <div>
              <p className="font-bold mb-2">
                Days
              </p>

              <div className="grid gap-2 sm:grid-cols-4">
                {WEEKDAYS.map(
                  (dayName) => {
                    const weekday =
                      WEEKDAY_MAP[
                        dayName
                      ];

                    const checked =
                      recurringWeekdays.includes(
                        weekday
                      );

                    return (
                      <label
                        key={dayName}
                        className="border rounded-xl p-3 flex items-center gap-2 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={
                            checked
                          }
                          onChange={() =>
                            toggleRecurringWeekday(
                              weekday
                            )
                          }
                        />

                        <span>
                          {dayName}
                        </span>
                      </label>
                    );
                  }
                )}
              </div>
            </div>

            <button
              onClick={addRecurringShopBlock}
              className="bg-black text-white px-4 py-3 rounded-xl font-bold"
            >
              Save Recurring Block
            </button>
          </div>

          <div className="space-y-2">
            <h3 className="text-xl font-bold">
              Upcoming Shop-Wide Blocks
            </h3>

            {upcomingShopBlockedTimes.length ===
            0 ? (
              <p className="text-gray-500">
                No upcoming shop-wide closures
                or breaks.
              </p>
            ) : (
              upcomingShopBlockedTimes.map(
                (block) => (
                  <div
                    key={block.id}
                    className="border rounded-xl p-3 flex justify-between items-center gap-4"
                  >
                    <div>
                      <p className="font-bold">
                        {block.reason}
                      </p>

                      <p className="text-sm text-gray-600">
                        {isFullDay(block)
                          ? formatDate(
                              block.start_datetime
                            )
                          : `${formatDateTime(
                              block.start_datetime
                            )} - ${formatDateTime(
                              block.end_datetime
                            )}`}
                      </p>

                      {block.series_id && (
                        <p className="text-xs text-gray-500 mt-1">
                          Recurring
                        </p>
                      )}
                    </div>

                    <div className="flex flex-wrap gap-2 justify-end">
                      <button
                        onClick={() =>
                          deleteShopBlockedTime(
                            block
                          )
                        }
                        className="bg-red-500 text-white px-3 py-2 rounded"
                      >
                        Delete This One
                      </button>

                      {block.series_id && (
                        <button
                          onClick={() =>
                            deleteShopBlockedSeries(
                              block
                            )
                          }
                          className="bg-red-700 text-white px-3 py-2 rounded"
                        >
                          Delete Series
                        </button>
                      )}
                    </div>
                  </div>
                )
              )
            )}
          </div>
        </div>

        {/* INDIVIDUAL STAFF SETTINGS */}

        <div className="bg-white p-6 rounded-2xl shadow-lg border border-indigo-200 space-y-4">
          <h2 className="text-2xl font-bold">
            Staff Member
          </h2>

          <p className="text-gray-600">
            Choose the staff member whose
            services, availability, and blocked
            time you want to manage.
          </p>

          {barbers.length === 0 ? (
            <div className="space-y-3">
              <p className="text-gray-500">
                No staff members found.
              </p>

              <a
                href={`/${shopSlug}/admin/staff`}
                className="inline-block bg-black text-white px-4 py-3 rounded-xl font-bold"
              >
                Add Staff
              </a>
            </div>
          ) : (
            <select
              value={selectedBarberId}
              onChange={(event) =>
                handleBarberChange(
                  event.target.value
                )
              }
              className="border p-3 rounded w-full"
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
          )}
        </div>

        {selectedBarber && (
          <>
            <div className="bg-white p-6 rounded-2xl shadow-lg border border-indigo-200 space-y-4">
              <h2 className="text-2xl font-bold">
                Services
              </h2>

              <p className="text-gray-600">
                Assign services to{" "}
                <strong>
                  {selectedBarber.name}
                </strong>{" "}
                from the shop's master service
                list.
              </p>

              <select
                value={serviceName}
                onChange={(event) =>
                  setServiceName(
                    event.target.value
                  )
                }
                className="border p-3 rounded w-full"
              >
                <option value="">
                  Choose service
                </option>

                {availableCatalogServices.map(
                  (service) => (
                    <option
                      key={service.id}
                      value={service.name}
                    >
                      {service.name}
                    </option>
                  )
                )}
              </select>

              {availableCatalogServices.length ===
                0 && (
                <p className="text-sm text-gray-500">
                  All shop services are already
                  assigned to{" "}
                  {selectedBarber.name}.
                </p>
              )}

              <input
                type="number"
                min="1"
                placeholder="Duration in minutes"
                value={serviceDuration}
                onChange={(event) =>
                  setServiceDuration(
                    event.target.value
                  )
                }
                className="border p-3 rounded w-full"
              />

              <input
                type="number"
                min="0"
                step="0.01"
                placeholder="Price"
                value={servicePrice}
                onChange={(event) =>
                  setServicePrice(
                    event.target.value
                  )
                }
                className="border p-3 rounded w-full"
              />

              <button
                onClick={addService}
                disabled={
                  !serviceName ||
                  !selectedBarberId
                }
                className={`px-4 py-3 rounded-xl font-bold ${
                  !serviceName ||
                  !selectedBarberId
                    ? "bg-gray-300 text-gray-600 cursor-not-allowed"
                    : "bg-black text-white"
                }`}
              >
                Assign Service
              </button>

              <div className="space-y-2">
                {selectedBarberServices.length ===
                0 ? (
                  <p className="text-gray-500">
                    No services assigned to{" "}
                    {selectedBarber.name}.
                  </p>
                ) : (
                  selectedBarberServices.map(
                    (service) => (
                      <div
                        key={service.id}
                        className="border rounded-xl p-4"
                      >
                        {editingServiceId ===
                        service.id ? (
                          <div className="space-y-3">
                            <select
                              value={
                                editedServiceName
                              }
                              onChange={(
                                event
                              ) =>
                                setEditedServiceName(
                                  event.target
                                    .value
                                )
                              }
                              className="border p-3 rounded w-full"
                            >
                              {serviceCatalog.map(
                                (
                                  catalogService
                                ) => (
                                  <option
                                    key={
                                      catalogService.id
                                    }
                                    value={
                                      catalogService.name
                                    }
                                  >
                                    {
                                      catalogService.name
                                    }
                                  </option>
                                )
                              )}
                            </select>

                            <input
                              type="number"
                              min="1"
                              value={
                                editedServiceDuration
                              }
                              onChange={(
                                event
                              ) =>
                                setEditedServiceDuration(
                                  event.target
                                    .value
                                )
                              }
                              className="border p-3 rounded w-full"
                              placeholder="Duration in minutes"
                            />

                            <input
                              type="number"
                              min="0"
                              step="0.01"
                              value={
                                editedServicePrice
                              }
                              onChange={(
                                event
                              ) =>
                                setEditedServicePrice(
                                  event.target
                                    .value
                                )
                              }
                              className="border p-3 rounded w-full"
                              placeholder="Price"
                            />

                            <div className="flex gap-2">
                              <button
                                onClick={() =>
                                  updateService(
                                    service.id
                                  )
                                }
                                className="bg-black text-white px-4 py-2 rounded-xl"
                              >
                                Save
                              </button>

                              <button
                                onClick={
                                  cancelEditingService
                                }
                                className="bg-gray-200 px-4 py-2 rounded-xl"
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div className="flex justify-between items-center gap-4">
                            <div>
                              <p className="font-bold">
                                {
                                  service.name
                                }
                              </p>

                              <p className="text-sm text-gray-600">
                                {
                                  service.duration_minutes
                                }{" "}
                                minutes · $
                                {Number(
                                  service.price
                                ).toFixed(2)}
                              </p>
                            </div>

                            <div className="flex gap-2">
                              <button
                                onClick={() =>
                                  startEditingService(
                                    service
                                  )
                                }
                                className="bg-black text-white px-3 py-2 rounded"
                              >
                                Edit
                              </button>

                              <button
                                onClick={() =>
                                  deleteService(
                                    service
                                  )
                                }
                                className="bg-red-500 text-white px-3 py-2 rounded"
                              >
                                Remove
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    )
                  )
                )}
              </div>
            </div>

            <div className="bg-white p-6 rounded-2xl shadow-lg border border-indigo-200 space-y-4">
              <h2 className="text-2xl font-bold">
                Weekly Availability
              </h2>

              <p className="text-gray-600">
                Set the normal weekly schedule
                for{" "}
                <strong>
                  {selectedBarber.name}
                </strong>
                .
              </p>

              <select
                value={availabilityDay}
                onChange={(event) =>
                  setAvailabilityDay(
                    event.target.value
                  )
                }
                className="border p-3 rounded w-full"
              >
                {Object.keys(
                  WEEKDAY_MAP
                ).map((day) => (
                  <option
                    key={day}
                    value={day}
                  >
                    {day}
                  </option>
                ))}
              </select>

              <input
                type="time"
                value={availabilityStart}
                onChange={(event) =>
                  setAvailabilityStart(
                    event.target.value
                  )
                }
                className="border p-3 rounded w-full"
              />

              <input
                type="time"
                value={availabilityEnd}
                onChange={(event) =>
                  setAvailabilityEnd(
                    event.target.value
                  )
                }
                className="border p-3 rounded w-full"
              />

              <button
                onClick={addAvailabilityRule}
                className="bg-black text-white px-4 py-3 rounded-xl"
              >
                Save Availability
              </button>

              <div className="space-y-2">
                {selectedBarberAvailability.length ===
                0 ? (
                  <p className="text-gray-500">
                    No weekly availability for{" "}
                    {selectedBarber.name}.
                  </p>
                ) : (
                  selectedBarberAvailability.map(
                    (rule) => (
                      <div
                        key={rule.id}
                        className="border rounded-xl p-3 flex justify-between items-center"
                      >
                        <div>
                          {
                            WEEKDAY_NAMES[
                              rule.weekday
                            ]
                          }{" "}
                          ·{" "}
                          {formatTime(
                            rule.start_time
                          )}{" "}
                          -{" "}
                          {formatTime(
                            rule.end_time
                          )}
                        </div>

                        <button
                          onClick={() =>
                            deleteAvailabilityRule(
                              rule.id
                            )
                          }
                          className="bg-red-500 text-white px-3 py-1 rounded"
                        >
                          Delete
                        </button>
                      </div>
                    )
                  )
                )}
              </div>
            </div>

            <div className="bg-white p-6 rounded-2xl shadow-lg border border-indigo-200 space-y-4">
              <h2 className="text-2xl font-bold">
                Quick Block Time
              </h2>

              <p className="text-gray-600">
                Block a specific period for{" "}
                <strong>
                  {selectedBarber.name}
                </strong>
                .
              </p>

              <input
                value={blockReason}
                onChange={(event) =>
                  setBlockReason(
                    event.target.value
                  )
                }
                placeholder="Reason"
                className="border p-3 rounded w-full"
              />

              <input
                type="datetime-local"
                value={blockStart}
                onChange={(event) =>
                  setBlockStart(
                    event.target.value
                  )
                }
                className="border p-3 rounded w-full"
              />

              <input
                type="datetime-local"
                value={blockEnd}
                onChange={(event) =>
                  setBlockEnd(
                    event.target.value
                  )
                }
                className="border p-3 rounded w-full"
              />

              <button
                onClick={blockTime}
                className="bg-black text-white px-4 py-3 rounded-xl"
              >
                Block Time
              </button>
            </div>

            <div className="bg-white p-6 rounded-2xl shadow-lg border border-indigo-200 space-y-4">
              <h2 className="text-2xl font-bold">
                Full Day Block
              </h2>

              <p className="text-gray-600">
                Mark a vacation or closed day
                for{" "}
                <strong>
                  {selectedBarber.name}
                </strong>
                .
              </p>

              <input
                type="date"
                value={fullDayDate}
                onChange={(event) =>
                  setFullDayDate(
                    event.target.value
                  )
                }
                className="border p-3 rounded w-full"
              />

              <div className="flex gap-3">
                <button
                  onClick={() =>
                    blockFullDay(
                      "Vacation"
                    )
                  }
                  className="bg-black text-white px-4 py-3 rounded-xl"
                >
                  Vacation
                </button>

                <button
                  onClick={() =>
                    blockFullDay(
                      "Closed"
                    )
                  }
                  className="bg-red-600 text-white px-4 py-3 rounded-xl"
                >
                  Closed
                </button>
              </div>

              <div className="space-y-2">
                {selectedBarberBlockedTimes.length ===
                0 ? (
                  <p className="text-gray-500">
                    No upcoming blocked times
                    for{" "}
                    {selectedBarber.name}.
                  </p>
                ) : (
                  selectedBarberBlockedTimes.map(
                    (block) => (
                      <div
                        key={block.id}
                        className="border rounded-xl p-3 flex justify-between items-center"
                      >
                        <div>
                          {block.reason} ·{" "}
                          {isFullDay(block)
                            ? formatDate(
                                block.start_datetime
                              )
                            : formatDateTime(
                                block.start_datetime
                              )}
                        </div>

                        <button
                          onClick={() =>
                            deleteBlockedTime(
                              block.id
                            )
                          }
                          className="bg-red-500 text-white px-3 py-1 rounded"
                        >
                          Delete
                        </button>
                      </div>
                    )
                  )
                )}
              </div>
            </div>
          </>
        )}

        <a
          href={`/${shopSlug}/admin`}
          className="inline-flex items-center justify-center bg-blue-600 text-white px-5 py-3 rounded-xl font-bold shadow hover:bg-blue-700"
        >
          Admin Home
        </a>
      </div>
    </main>
  );
}
