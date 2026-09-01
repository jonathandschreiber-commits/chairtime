"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useParams, useRouter } from "next/navigation";
import styles from "./onboarding.module.css";

const API_BASE =
  "https://chairtime-production-94da.up.railway.app";

const DAYS = [
  { name: "Monday", weekday: 0 },
  { name: "Tuesday", weekday: 1 },
  { name: "Wednesday", weekday: 2 },
  { name: "Thursday", weekday: 3 },
  { name: "Friday", weekday: 4 },
  { name: "Saturday", weekday: 5 },
  { name: "Sunday", weekday: 6 },
];

function makeDefaultHours() {
  return DAYS.map((day) => ({
    ...day,
    open: day.weekday <= 4,
    start: "09:00",
    end: "17:00",
  }));
}

export default function OnboardingPage() {
  const params = useParams();
  const router = useRouter();

  const shopSlug = params.shop;

  const [currentStep, setCurrentStep] = useState(1);

  const [hours, setHours] = useState(
    makeDefaultHours()
  );

  const [existingRules, setExistingRules] =
    useState([]);

  const [staff, setStaff] = useState([]);
  const [services, setServices] = useState([]);

  const [newStaffName, setNewStaffName] =
    useState("");

  const [newServiceName, setNewServiceName] =
    useState("");

  const [loading, setLoading] = useState(true);

  const [savingHours, setSavingHours] =
    useState(false);

  const [addingStaff, setAddingStaff] =
    useState(false);

  const [addingService, setAddingService] =
    useState(false);

  const [message, setMessage] = useState("");

  const [assignedServices, setAssignedServices] =
    useState([]);

  const [availabilityRules, setAvailabilityRules] =
    useState([]);

  const [currentStaffIndex, setCurrentStaffIndex] =
    useState(0);

  const [staffServiceForm, setStaffServiceForm] =
    useState({});

  const [staffHours, setStaffHours] = useState(
    makeDefaultHours()
  );

  const [savingStaffSetup, setSavingStaffSetup] =
    useState(false);

  const [paymentPolicy, setPaymentPolicy] =
    useState("none");

  const [savingPaymentPolicy, setSavingPaymentPolicy] =
    useState(false);

  const [connectStatus, setConnectStatus] =
    useState(null);

  const [
    loadingConnectStatus,
    setLoadingConnectStatus,
  ] = useState(false);

  const [
    connectStatusError,
    setConnectStatusError,
  ] = useState("");

  const openDayCount = useMemo(() => {
    return hours.filter((day) => day.open).length;
  }, [hours]);

  const loadConnectStatus = useCallback(
    async () => {
      if (
        !shopSlug ||
        paymentPolicy === "none"
      ) {
        setConnectStatus(null);
        setConnectStatusError("");
        return;
      }

      setLoadingConnectStatus(true);
      setConnectStatusError("");

      try {
        const response = await fetch(
          "/api/billing/connect/status",
          {
            method: "GET",
            headers: {
              Accept: "application/json",
            },
            cache: "no-store",
          }
        );

        const data = await response
          .json()
          .catch(() => ({}));

        if (response.status === 401) {
          router.replace(
            `/login?next=${encodeURIComponent(
              `/${shopSlug}/onboarding`
            )}`
          );

          return;
        }

        if (!response.ok) {
          throw new Error(
            data.error ||
              data.detail ||
              "Could not check your payment account."
          );
        }

        setConnectStatus(data);
      } catch (error) {
        console.error(error);

        setConnectStatusError(
          error instanceof Error
            ? error.message
            : "Could not check your payment account."
        );
      } finally {
        setLoadingConnectStatus(false);
      }
    },
    [
      paymentPolicy,
      router,
      shopSlug,
    ]
  );

  useEffect(() => {
    if (!shopSlug) return;

    loadOnboardingData();
  }, [shopSlug]);

  useEffect(() => {
    if (
      !shopSlug ||
      currentStep !== 5 ||
      paymentPolicy === "none"
    ) {
      return;
    }

    loadConnectStatus();
  }, [
    currentStep,
    loadConnectStatus,
    paymentPolicy,
    shopSlug,
  ]);

  async function loadOnboardingData() {
    try {
      const query =
        "?shop_slug=" +
        encodeURIComponent(shopSlug);

      const [
        hoursResponse,
        staffResponse,
        servicesResponse,
        assignedServicesResponse,
        availabilityResponse,
        shopResponse,
      ] = await Promise.all([
        fetch(
          `${API_BASE}/api/shop-availability-rules${query}`,
          {
            cache: "no-store",
          }
        ),
        fetch(
          `${API_BASE}/api/barbers${query}`,
          {
            cache: "no-store",
          }
        ),
        fetch(
          `${API_BASE}/api/service-catalog${query}`,
          {
            cache: "no-store",
          }
        ),
        fetch(
          `${API_BASE}/api/services${query}`,
          {
            cache: "no-store",
          }
        ),
        fetch(
          `${API_BASE}/api/availability-rules${query}`,
          {
            cache: "no-store",
          }
        ),
        fetch(
          `${API_BASE}/api/shops${query}`,
          {
            cache: "no-store",
          }
        ),
      ]);

      if (!hoursResponse.ok) {
        throw new Error(
          "Could not load your shop hours."
        );
      }

      if (!staffResponse.ok) {
        throw new Error(
          "Could not load your staff."
        );
      }

      if (!servicesResponse.ok) {
        throw new Error(
          "Could not load your services."
        );
      }

      if (!assignedServicesResponse.ok) {
        throw new Error(
          "Could not load staff services."
        );
      }

      if (!availabilityResponse.ok) {
        throw new Error(
          "Could not load staff schedules."
        );
      }

      if (!shopResponse.ok) {
        throw new Error(
          "Could not load your payment preference."
        );
      }

      const hoursData =
        await hoursResponse.json();

      const staffData =
        await staffResponse.json();

      const servicesData =
        await servicesResponse.json();

      const assignedServicesData =
        await assignedServicesResponse.json();

      const availabilityData =
        await availabilityResponse.json();

      const shopData =
        await shopResponse.json();

      const currentShop =
        Array.isArray(shopData) && shopData.length > 0
          ? shopData[0]
          : null;

      setPaymentPolicy(
        currentShop?.payment_policy || "none"
      );

      setExistingRules(hoursData);
      setStaff(staffData);
      setServices(servicesData);

      setAssignedServices(
        assignedServicesData
      );

      setAvailabilityRules(
        availabilityData
      );

      const normalizedHours =
        hoursData.length > 0
          ? DAYS.map((day) => {
              const rule =
                hoursData.find(
                  (item) =>
                    item.weekday ===
                    day.weekday
                );

              if (!rule) {
                return {
                  ...day,
                  open: false,
                  start: "09:00",
                  end: "17:00",
                };
              }

              return {
                ...day,
                open: true,

                start: String(
                  rule.start_time
                ).slice(0, 5),

                end: String(
                  rule.end_time
                ).slice(0, 5),
              };
            })
          : makeDefaultHours();

      setHours(normalizedHours);

      if (hoursData.length === 0) {
        setCurrentStep(1);
      } else if (staffData.length === 0) {
        setCurrentStep(2);
      } else if (servicesData.length === 0) {
        setCurrentStep(3);
      } else {
        const firstIncompleteIndex =
          staffData.findIndex(
            (person) => {
              const hasService =
                assignedServicesData.some(
                  (service) =>
                    service.barber_id ===
                    person.id
                );

              const hasHours =
                availabilityData.some(
                  (rule) =>
                    rule.barber_id ===
                    person.id
                );

              return !hasService || !hasHours;
            }
          );

        if (firstIncompleteIndex === -1) {
          setCurrentStep(5);
        } else {
          setCurrentStep(4);

          setCurrentStaffIndex(
            firstIncompleteIndex
          );

          prepareStaffEditor(
            staffData[firstIncompleteIndex],
            servicesData,
            assignedServicesData,
            availabilityData,
            normalizedHours
          );
        }
      }
    } catch (error) {
      console.error(error);

      setMessage(
        error instanceof Error
          ? error.message
          : "Could not load your setup."
      );
    } finally {
      setLoading(false);
    }
  }

  function prepareStaffEditor(
    person,
    catalogServices = services,
    currentAssignments = assignedServices,
    currentAvailability = availabilityRules,
    shopHours = hours
  ) {
    if (!person) return;

    const nextServiceForm = {};

    for (const catalogService of catalogServices) {
      const existing =
        currentAssignments.find(
          (service) =>
            service.barber_id ===
              person.id &&
            String(service.name)
              .trim()
              .toLowerCase() ===
              String(catalogService.name)
                .trim()
                .toLowerCase()
        );

      nextServiceForm[
        catalogService.id
      ] = {
        selected: Boolean(existing),

        duration: String(
          existing?.duration_minutes ?? 30
        ),

        price:
          existing?.price === undefined ||
          existing?.price === null
            ? ""
            : String(existing.price),
      };
    }

    setStaffServiceForm(
      nextServiceForm
    );

    const personRules =
      currentAvailability.filter(
        (rule) =>
          rule.barber_id === person.id
      );

    if (personRules.length > 0) {
      setStaffHours(
        DAYS.map((day) => {
          const rule = personRules.find(
            (item) =>
              item.weekday === day.weekday
          );

          if (!rule) {
            return {
              ...day,
              open: false,
              start: "09:00",
              end: "17:00",
            };
          }

          return {
            ...day,
            open: true,

            start: String(
              rule.start_time
            ).slice(0, 5),

            end: String(
              rule.end_time
            ).slice(0, 5),
          };
        })
      );
    } else {
      setStaffHours(
        shopHours.map((day) => ({
          ...day,
        }))
      );
    }
  }

  function updateDay(
    weekday,
    field,
    value
  ) {
    setHours((current) =>
      current.map((day) =>
        day.weekday === weekday
          ? {
              ...day,
              [field]: value,
            }
          : day
      )
    );

    setMessage("");
  }

  async function saveHours() {
    if (savingHours) return;

    const invalidDay = hours.find(
      (day) =>
        day.open &&
        (!day.start ||
          !day.end ||
          day.start >= day.end)
    );

    if (invalidDay) {
      setMessage(
        `${invalidDay.name}: closing time must be later than opening time.`
      );

      return;
    }

    if (openDayCount === 0) {
      setMessage(
        "Choose at least one day your business is open."
      );

      return;
    }

    setSavingHours(true);
    setMessage("");

    try {
      for (const rule of existingRules) {
        const deleteResponse = await fetch(
          `${API_BASE}/api/shop-availability-rules/${encodeURIComponent(
            rule.id
          )}`,
          {
            method: "DELETE",
          }
        );

        if (!deleteResponse.ok) {
          throw new Error(
            "Could not update your shop hours."
          );
        }
      }

      for (const day of hours) {
        if (!day.open) continue;

        const response = await fetch(
          `${API_BASE}/api/shop-availability-rules`,
          {
            method: "POST",

            headers: {
              "Content-Type":
                "application/json",
            },

            body: JSON.stringify({
              shop_slug: shopSlug,
              weekday: day.weekday,
              start_time: `${day.start}:00`,
              end_time: `${day.end}:00`,
            }),
          }
        );

        if (!response.ok) {
          const error = await response
            .json()
            .catch(() => ({}));

          throw new Error(
            typeof error.detail === "string"
              ? error.detail
              : `Could not save ${day.name}.`
          );
        }
      }

      const refreshedResponse =
        await fetch(
          `${API_BASE}/api/shop-availability-rules?shop_slug=${encodeURIComponent(
            shopSlug
          )}`,
          {
            cache: "no-store",
          }
        );

      if (refreshedResponse.ok) {
        setExistingRules(
          await refreshedResponse.json()
        );
      }

      setMessage("");
      setCurrentStep(2);
    } catch (error) {
      console.error(error);

      setMessage(
        error instanceof Error
          ? error.message
          : "Could not save your shop hours."
      );
    } finally {
      setSavingHours(false);
    }
  }

  async function addStaffMember(event) {
    event?.preventDefault();

    if (addingStaff) return;

    const cleanName =
      newStaffName.trim();

    if (!cleanName) {
      setMessage(
        "Enter the staff member's name."
      );

      return;
    }

    setAddingStaff(true);
    setMessage("");

    try {
      const existingStaff =
        staff[0];

      const response = await fetch(
        `${API_BASE}/api/barbers`,
        {
          method: "POST",

          headers: {
            "Content-Type":
              "application/json",
          },

          body: JSON.stringify({
            name: cleanName,

            shop_name:
              existingStaff?.shop_name ||
              shopSlug,

            phone: "",

            timezone:
              existingStaff?.timezone ||
              "America/New_York",

            shop_slug: shopSlug,
          }),
        }
      );

      if (!response.ok) {
        const error = await response
          .json()
          .catch(() => ({}));

        throw new Error(
          typeof error.detail === "string"
            ? error.detail
            : "Could not add staff member."
        );
      }

      setNewStaffName("");

      await reloadStaff();

      setMessage(
        `${cleanName} added.`
      );
    } catch (error) {
      console.error(error);

      setMessage(
        error instanceof Error
          ? error.message
          : "Could not add staff member."
      );
    } finally {
      setAddingStaff(false);
    }
  }

  async function reloadStaff() {
    const response = await fetch(
      `${API_BASE}/api/barbers?shop_slug=${encodeURIComponent(
        shopSlug
      )}`,
      {
        cache: "no-store",
      }
    );

    if (!response.ok) {
      throw new Error(
        "Could not reload your staff."
      );
    }

    setStaff(
      await response.json()
    );
  }

  async function removeStaffMember(
    person
  ) {
    const confirmed = window.confirm(
      `Remove ${person.name} from your staff?`
    );

    if (!confirmed) return;

    setMessage("");

    try {
      const response = await fetch(
        `${API_BASE}/api/barbers/${encodeURIComponent(
          person.id
        )}`,
        {
          method: "DELETE",
        }
      );

      if (!response.ok) {
        const error = await response
          .json()
          .catch(() => ({}));

        throw new Error(
          typeof error.detail === "string"
            ? error.detail
            : "Could not remove staff member."
        );
      }

      await reloadStaff();

      setMessage(
        `${person.name} removed.`
      );
    } catch (error) {
      console.error(error);

      setMessage(
        error instanceof Error
          ? error.message
          : "Could not remove staff member."
      );
    }
  }

  function continueFromStaff() {
    if (staff.length === 0) {
      setMessage(
        "Add at least one person who customers can book with."
      );

      return;
    }

    setMessage("");
    setCurrentStep(3);
  }

  async function addService(event) {
    event?.preventDefault();

    if (addingService) return;

    const cleanName =
      newServiceName.trim();

    if (!cleanName) {
      setMessage(
        "Enter a service name."
      );

      return;
    }

    setAddingService(true);
    setMessage("");

    try {
      const response = await fetch(
        `${API_BASE}/api/service-catalog`,
        {
          method: "POST",

          headers: {
            "Content-Type":
              "application/json",
          },

          body: JSON.stringify({
            shop_slug: shopSlug,
            name: cleanName,
          }),
        }
      );

      if (!response.ok) {
        const error = await response
          .json()
          .catch(() => ({}));

        throw new Error(
          typeof error.detail === "string"
            ? error.detail
            : "Could not add service."
        );
      }

      setNewServiceName("");

      await reloadServices();

      setMessage(
        `${cleanName} added.`
      );
    } catch (error) {
      console.error(error);

      setMessage(
        error instanceof Error
          ? error.message
          : "Could not add service."
      );
    } finally {
      setAddingService(false);
    }
  }

  async function reloadServices() {
    const response = await fetch(
      `${API_BASE}/api/service-catalog?shop_slug=${encodeURIComponent(
        shopSlug
      )}`,
      {
        cache: "no-store",
      }
    );

    if (!response.ok) {
      throw new Error(
        "Could not reload your services."
      );
    }

    setServices(
      await response.json()
    );
  }

  async function removeService(
    service
  ) {
    const confirmed = window.confirm(
      `Remove ${service.name} from your service list?`
    );

    if (!confirmed) return;

    setMessage("");

    try {
      const response = await fetch(
        `${API_BASE}/api/service-catalog/${encodeURIComponent(
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

        if (
          error.detail &&
          typeof error.detail === "object"
        ) {
          const assignedStaff =
            error.detail.assigned_staff || [];

          if (
            assignedStaff.length > 0
          ) {
            throw new Error(
              `${service.name} is already assigned to ${assignedStaff.join(
                ", "
              )}.`
            );
          }
        }

        throw new Error(
          typeof error.detail === "string"
            ? error.detail
            : "Could not remove service."
        );
      }

      await reloadServices();

      setMessage(
        `${service.name} removed.`
      );
    } catch (error) {
      console.error(error);

      setMessage(
        error instanceof Error
          ? error.message
          : "Could not remove service."
      );
    }
  }

  function continueFromServices() {
    if (services.length === 0) {
      setMessage(
        "Add at least one service customers can book."
      );

      return;
    }

    setMessage("");
    setCurrentStaffIndex(0);

    prepareStaffEditor(
      staff[0],
      services,
      assignedServices,
      availabilityRules,
      hours
    );

    setCurrentStep(4);
  }

  function goToStep(step) {
    setMessage("");
    setCurrentStep(step);
  }

  function updateStaffService(
    catalogServiceId,
    field,
    value
  ) {
    setStaffServiceForm(
      (current) => ({
        ...current,

        [catalogServiceId]: {
          ...current[
            catalogServiceId
          ],

          [field]: value,
        },
      })
    );

    setMessage("");
  }

  function updateStaffHours(
    weekday,
    field,
    value
  ) {
    setStaffHours((current) =>
      current.map((day) =>
        day.weekday === weekday
          ? {
              ...day,
              [field]: value,
            }
          : day
      )
    );

    setMessage("");
  }

  async function refreshStaffSetupData() {
    const query =
      "?shop_slug=" +
      encodeURIComponent(shopSlug);

    const [
      servicesResponse,
      availabilityResponse,
    ] = await Promise.all([
      fetch(
        `${API_BASE}/api/services${query}`,
        {
          cache: "no-store",
        }
      ),

      fetch(
        `${API_BASE}/api/availability-rules${query}`,
        {
          cache: "no-store",
        }
      ),
    ]);

    if (
      !servicesResponse.ok ||
      !availabilityResponse.ok
    ) {
      throw new Error(
        "Could not reload staff setup."
      );
    }

    const nextAssignedServices =
      await servicesResponse.json();

    const nextAvailabilityRules =
      await availabilityResponse.json();

    setAssignedServices(
      nextAssignedServices
    );

    setAvailabilityRules(
      nextAvailabilityRules
    );

    return {
      nextAssignedServices,
      nextAvailabilityRules,
    };
  }

  async function saveCurrentStaffSetup() {
    if (savingStaffSetup) return;

    const person =
      staff[currentStaffIndex];

    if (!person) {
      setMessage(
        "Could not identify the staff member."
      );

      return;
    }

    const selectedCatalogServices =
      services.filter(
        (service) =>
          staffServiceForm[service.id]
            ?.selected
      );

    if (
      selectedCatalogServices.length === 0
    ) {
      setMessage(
        `Choose at least one service for ${person.name}.`
      );

      return;
    }

    for (
      const catalogService
      of selectedCatalogServices
    ) {
      const form =
        staffServiceForm[
          catalogService.id
        ];

      const duration =
        Number(form?.duration);

      const price =
        Number(form?.price);

      if (
        !duration ||
        duration <= 0
      ) {
        setMessage(
          `Enter a valid duration for ${catalogService.name}.`
        );

        return;
      }

      if (
        form?.price === "" ||
        Number.isNaN(price) ||
        price < 0
      ) {
        setMessage(
          `Enter a valid price for ${catalogService.name}.`
        );

        return;
      }
    }

    const invalidDay =
      staffHours.find(
        (day) =>
          day.open &&
          (!day.start ||
            !day.end ||
            day.start >= day.end)
      );

    if (invalidDay) {
      setMessage(
        `${person.name} — ${invalidDay.name}: closing time must be later than opening time.`
      );

      return;
    }

    if (
      !staffHours.some(
        (day) => day.open
      )
    ) {
      setMessage(
        `Choose at least one working day for ${person.name}.`
      );

      return;
    }

    setSavingStaffSetup(true);
    setMessage("");

    try {
      for (const catalogService of services) {
        const form =
          staffServiceForm[
            catalogService.id
          ] || {
            selected: false,
            duration: "30",
            price: "",
          };

        const existing =
          assignedServices.find(
            (service) =>
              service.barber_id ===
                person.id &&
              String(service.name)
                .trim()
                .toLowerCase() ===
                String(
                  catalogService.name
                )
                  .trim()
                  .toLowerCase()
          );

        if (form.selected) {
          const payload = {
            name: catalogService.name,

            duration_minutes: Number(
              form.duration
            ),

            price: Number(
              form.price
            ),
          };

          if (existing) {
            const response =
              await fetch(
                `${API_BASE}/api/services/${encodeURIComponent(
                  existing.id
                )}`,
                {
                  method: "PATCH",

                  headers: {
                    "Content-Type":
                      "application/json",
                  },

                  body: JSON.stringify(
                    payload
                  ),
                }
              );

            if (!response.ok) {
              throw new Error(
                `Could not update ${catalogService.name} for ${person.name}.`
              );
            }
          } else {
            const response =
              await fetch(
                `${API_BASE}/api/services`,
                {
                  method: "POST",

                  headers: {
                    "Content-Type":
                      "application/json",
                  },

                  body: JSON.stringify({
                    shop_slug: shopSlug,
                    barber_id: person.id,
                    ...payload,
                  }),
                }
              );

            if (!response.ok) {
              const error =
                await response
                  .json()
                  .catch(() => ({}));

              throw new Error(
                typeof error.detail ===
                  "string"
                  ? error.detail
                  : `Could not assign ${catalogService.name} to ${person.name}.`
              );
            }
          }
        } else if (existing) {
          const response =
            await fetch(
              `${API_BASE}/api/services/${encodeURIComponent(
                existing.id
              )}`,
              {
                method: "DELETE",
              }
            );

          if (!response.ok) {
            throw new Error(
              `Could not remove ${catalogService.name} from ${person.name}.`
            );
          }
        }
      }

      const existingPersonRules =
        availabilityRules.filter(
          (rule) =>
            rule.barber_id ===
            person.id
        );

      for (
        const rule
        of existingPersonRules
      ) {
        const response =
          await fetch(
            `${API_BASE}/api/availability-rules/${encodeURIComponent(
              rule.id
            )}`,
            {
              method: "DELETE",
            }
          );

        if (!response.ok) {
          throw new Error(
            `Could not update ${person.name}'s schedule.`
          );
        }
      }

      for (const day of staffHours) {
        if (!day.open) continue;

        const response =
          await fetch(
            `${API_BASE}/api/availability-rules`,
            {
              method: "POST",

              headers: {
                "Content-Type":
                  "application/json",
              },

              body: JSON.stringify({
                shop_slug: shopSlug,
                barber_id: person.id,
                weekday: day.weekday,

                start_time:
                  `${day.start}:00`,

                end_time:
                  `${day.end}:00`,
              }),
            }
          );

        if (!response.ok) {
          const error =
            await response
              .json()
              .catch(() => ({}));

          throw new Error(
            typeof error.detail ===
              "string"
              ? error.detail
              : `Could not save ${person.name}'s ${day.name} hours.`
          );
        }
      }

      const {
        nextAssignedServices,
        nextAvailabilityRules,
      } =
        await refreshStaffSetupData();

      const nextIndex =
        currentStaffIndex + 1;

      if (nextIndex < staff.length) {
        setCurrentStaffIndex(
          nextIndex
        );

        prepareStaffEditor(
          staff[nextIndex],
          services,
          nextAssignedServices,
          nextAvailabilityRules,
          hours
        );

        setMessage(
          `${person.name} is ready. Now set up ${staff[nextIndex].name}.`
        );
      } else {
        setMessage("");
        setCurrentStep(5);
      }
    } catch (error) {
      console.error(error);

      setMessage(
        error instanceof Error
          ? error.message
          : "Could not save this staff setup."
      );
    } finally {
      setSavingStaffSetup(false);
    }
  }

  function goBackFromStaffSetup() {
    if (currentStaffIndex === 0) {
      goToStep(3);
      return;
    }

    const previousIndex =
      currentStaffIndex - 1;

    setCurrentStaffIndex(
      previousIndex
    );

    prepareStaffEditor(
      staff[previousIndex],
      services,
      assignedServices,
      availabilityRules,
      hours
    );

    setMessage("");
  }

  async function savePaymentPreference(
    continueToReview = true
  ) {
    if (savingPaymentPolicy) return false;

    setSavingPaymentPolicy(true);
    setMessage("");

    try {
      const response = await fetch(
        `${API_BASE}/api/shops/${encodeURIComponent(
          shopSlug
        )}/payment-policy`,
        {
          method: "PATCH",

          headers: {
            "Content-Type": "application/json",
          },

          body: JSON.stringify({
            payment_policy: paymentPolicy,
          }),
        }
      );

      if (!response.ok) {
        const error = await response
          .json()
          .catch(() => ({}));

        throw new Error(
          typeof error.detail === "string"
            ? error.detail
            : "Could not save your payment preference."
        );
      }

      setMessage("");

      if (continueToReview) {
        setCurrentStep(6);
      }

      return true;
    } catch (error) {
      console.error(error);

      setMessage(
        error instanceof Error
          ? error.message
          : "Could not save your payment preference."
      );

      return false;
    } finally {
      setSavingPaymentPolicy(false);
    }
  }

  function openBookingPage() {
    window.open(
      `/${shopSlug}`,
      "_blank",
      "noopener,noreferrer"
    );
  }

  function finishOnboarding() {
    router.push(
      `/${shopSlug}/admin`
    );
  }

  if (loading) {
    return (
      <main className={styles.page}>
        <div className={styles.loading}>
          Loading your setup...
        </div>
      </main>
    );
  }

  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <header className={styles.header}>
          <div>
            <p className={styles.eyebrow}>
              LET&apos;S GET YOU READY
            </p>

            <h1 className={styles.title}>
              Set up your business
            </h1>

            <p className={styles.subtitle}>
              We&apos;ll walk you through
              everything. It only takes a few
              minutes.
            </p>
          </div>

          <div className={styles.stepBadge}>
            Step {currentStep} of 6
          </div>
        </header>

        <Progress
          currentStep={currentStep}
        />

        {currentStep === 1 && (
          <HoursStep
            hours={hours}
            openDayCount={openDayCount}
            updateDay={updateDay}
            saveHours={saveHours}
            savingHours={savingHours}
            message={message}
          />
        )}

        {currentStep === 2 && (
          <StaffStep
            staff={staff}
            newStaffName={newStaffName}
            setNewStaffName={
              setNewStaffName
            }
            addingStaff={addingStaff}
            addStaffMember={addStaffMember}
            removeStaffMember={
              removeStaffMember
            }
            continueFromStaff={
              continueFromStaff
            }
            goBack={() =>
              goToStep(1)
            }
            message={message}
          />
        )}

        {currentStep === 3 && (
          <ServicesStep
            services={services}
            newServiceName={
              newServiceName
            }
            setNewServiceName={
              setNewServiceName
            }
            addingService={
              addingService
            }
            addService={addService}
            removeService={removeService}
            continueFromServices={
              continueFromServices
            }
            goBack={() =>
              goToStep(2)
            }
            message={message}
          />
        )}

        {currentStep === 4 && (
          <ScheduleStep
            staff={staff}
            services={services}
            currentStaffIndex={
              currentStaffIndex
            }
            staffServiceForm={
              staffServiceForm
            }
            updateStaffService={
              updateStaffService
            }
            staffHours={staffHours}
            updateStaffHours={
              updateStaffHours
            }
            savingStaffSetup={
              savingStaffSetup
            }
            saveCurrentStaffSetup={
              saveCurrentStaffSetup
            }
            goBack={
              goBackFromStaffSetup
            }
            message={message}
          />
        )}

        {currentStep === 5 && (
          <PaymentsStep
            paymentPolicy={paymentPolicy}
            setPaymentPolicy={(value) => {
              setPaymentPolicy(value);
              setMessage("");
            }}
            savingPaymentPolicy={
              savingPaymentPolicy
            }
            connectStatus={connectStatus}
            loadingConnectStatus={
              loadingConnectStatus
            }
            connectStatusError={
              connectStatusError
            }
            refreshConnectStatus={
              loadConnectStatus
            }
            savePaymentPreference={
              savePaymentPreference
            }
            goBack={() => {
              const lastIndex =
                Math.max(
                  staff.length - 1,
                  0
                );

              setCurrentStaffIndex(
                lastIndex
              );

              prepareStaffEditor(
                staff[lastIndex],
                services,
                assignedServices,
                availabilityRules,
                hours
              );

              goToStep(4);
            }}
            message={message}
          />
        )}

        {currentStep === 6 && (
          <ReviewStep
            shopSlug={shopSlug}
            staff={staff}
            services={services}
            assignedServices={
              assignedServices
            }
            openBookingPage={
              openBookingPage
            }
            finishOnboarding={
              finishOnboarding
            }
            goBack={() =>
              goToStep(5)
            }
          />
        )}

        <p className={styles.helpText}>
          Don&apos;t worry — everything here
          can be changed later from your
          Admin pages.
        </p>
      </div>
    </main>
  );
}

function Progress({
  currentStep,
}) {
  const steps = [
    "Hours",
    "Staff",
    "Services",
    "Schedules",
    "Payments",
    "Review",
  ];

  return (
    <section className={styles.progressCard}>
      {steps.map((label, index) => {
        const stepNumber = index + 1;

        const isActive =
          stepNumber === currentStep;

        const isDone =
          stepNumber < currentStep;

        return (
          <div
            key={label}
            className={
              styles.progressGroup
            }
          >
            <div
              className={[
                styles.progressStep,

                isActive
                  ? styles.progressActive
                  : "",

                isDone
                  ? styles.progressDone
                  : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              <span>
                {isDone
                  ? "✓"
                  : stepNumber}
              </span>

              <strong>{label}</strong>
            </div>

            {index <
              steps.length - 1 && (
              <div
                className={[
                  styles.progressLine,

                  isDone
                    ? styles.progressLineDone
                    : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
              />
            )}
          </div>
        );
      })}
    </section>
  );
}

function HoursStep({
  hours,
  openDayCount,
  updateDay,
  saveHours,
  savingHours,
  message,
}) {
  return (
    <section className={styles.mainCard}>
      <div className={styles.cardHeading}>
        <div className={styles.icon}>
          🕒
        </div>

        <div>
          <p className={styles.stepLabel}>
            STEP 1
          </p>

          <h2 className={styles.cardTitle}>
            When is your business open?
          </h2>

          <p className={styles.cardText}>
            Choose your normal weekly hours.
            You can always change them later.
          </p>
        </div>
      </div>

      <Message message={message} />

      <div className={styles.days}>
        {hours.map((day) => (
          <div
            key={day.weekday}
            className={`${styles.dayCard} ${
              day.open
                ? styles.dayOpen
                : styles.dayClosed
            }`}
          >
            <div className={styles.dayTop}>
              <div>
                <strong
                  className={styles.dayName}
                >
                  {day.name}
                </strong>

                <p
                  className={
                    day.open
                      ? styles.openText
                      : styles.closedText
                  }
                >
                  {day.open
                    ? "Open"
                    : "Closed"}
                </p>
              </div>

              <label
                className={styles.switch}
              >
                <input
                  type="checkbox"
                  checked={day.open}
                  onChange={(event) =>
                    updateDay(
                      day.weekday,
                      "open",
                      event.target.checked
                    )
                  }
                />

                <span
                  className={
                    styles.slider
                  }
                />
              </label>
            </div>

            {day.open ? (
              <div
                className={
                  styles.timeGrid
                }
              >
                <label>
                  <span>Opens</span>

                  <input
                    type="time"
                    value={day.start}
                    onChange={(event) =>
                      updateDay(
                        day.weekday,
                        "start",
                        event.target.value
                      )
                    }
                  />
                </label>

                <label>
                  <span>Closes</span>

                  <input
                    type="time"
                    value={day.end}
                    onChange={(event) =>
                      updateDay(
                        day.weekday,
                        "end",
                        event.target.value
                      )
                    }
                  />
                </label>
              </div>
            ) : (
              <div
                className={
                  styles.closedMessage
                }
              >
                No appointments will be
                offered on {day.name}.
              </div>
            )}
          </div>
        ))}
      </div>

      <div className={styles.footer}>
        <div>
          <strong>
            {openDayCount} days open
          </strong>

          <p>
            These become your normal shop
            hours.
          </p>
        </div>

        <button
          type="button"
          onClick={saveHours}
          disabled={savingHours}
          className={
            styles.continueButton
          }
        >
          {savingHours
            ? "Saving..."
            : "Save & Continue →"}
        </button>
      </div>
    </section>
  );
}

function StaffStep({
  staff,
  newStaffName,
  setNewStaffName,
  addingStaff,
  addStaffMember,
  removeStaffMember,
  continueFromStaff,
  goBack,
  message,
}) {
  return (
    <section
      className={`${styles.mainCard} ${styles.staffCard}`}
    >
      <div className={styles.cardHeading}>
        <div
          className={`${styles.icon} ${styles.staffIcon}`}
        >
          👥
        </div>

        <div>
          <p
            className={`${styles.stepLabel} ${styles.staffStepLabel}`}
          >
            STEP 2
          </p>

          <h2 className={styles.cardTitle}>
            Who takes appointments?
          </h2>

          <p className={styles.cardText}>
            Add yourself and anyone else
            customers can book with.
          </p>
        </div>
      </div>

      <Message message={message} />

      <form
        className={
          styles.addPersonCard
        }
        onSubmit={addStaffMember}
      >
        <label
          className={styles.formLabel}
          htmlFor="staffName"
        >
          Staff member&apos;s name
        </label>

        <div className={styles.addRow}>
          <input
            id="staffName"
            type="text"
            value={newStaffName}

            onChange={(event) =>
              setNewStaffName(
                event.target.value
              )
            }

            placeholder="Example: Maria"
            className={styles.textInput}
            disabled={addingStaff}
          />

          <button
            type="submit"
            disabled={addingStaff}
            className={
              styles.staffAddButton
            }
          >
            {addingStaff
              ? "Adding..."
              : "+ Add Staff"}
          </button>
        </div>
      </form>

      <div className={styles.peopleList}>
        {staff.length === 0 ? (
          <div
            className={styles.emptyState}
          >
            <div
              className={
                styles.emptyIcon
              }
            >
              👋
            </div>

            <strong>
              Start with yourself
            </strong>

            <p>
              Add the first person customers
              can book with.
            </p>
          </div>
        ) : (
          staff.map((person) => (
            <div
              key={person.id}
              className={
                styles.personRow
              }
            >
              <div
                className={
                  styles.personAvatar
                }
              >
                {String(person.name)
                  .trim()
                  .slice(0, 1)
                  .toUpperCase()}
              </div>

              <div
                className={
                  styles.personInfo
                }
              >
                <strong>
                  {person.name}
                </strong>

                <span>
                  Ready for services and
                  schedule
                </span>
              </div>

              <div
                className={
                  styles.readyBadge
                }
              >
                ✓ Added
              </div>

              <button
                type="button"
                onClick={() =>
                  removeStaffMember(
                    person
                  )
                }
                className={
                  styles.removeButton
                }
              >
                Remove
              </button>
            </div>
          ))
        )}
      </div>

      <div className={styles.footer}>
        <button
          type="button"
          onClick={goBack}
          className={styles.backButton}
        >
          ← Back
        </button>

        <div
          className={
            styles.footerRight
          }
        >
          <div>
            <strong>
              {staff.length}{" "}
              {staff.length === 1
                ? "person"
                : "people"}{" "}
              added
            </strong>

            <p>
              You can add more staff later.
            </p>
          </div>

          <button
            type="button"
            onClick={
              continueFromStaff
            }
            className={
              styles.continueButton
            }
          >
            Continue to Services →
          </button>
        </div>
      </div>
    </section>
  );
}

function ServicesStep({
  services,
  newServiceName,
  setNewServiceName,
  addingService,
  addService,
  removeService,
  continueFromServices,
  goBack,
  message,
}) {
  return (
    <section
      className={`${styles.mainCard} ${styles.servicesCard}`}
    >
      <div className={styles.cardHeading}>
        <div
          className={`${styles.icon} ${styles.serviceIcon}`}
        >
          ✨
        </div>

        <div>
          <p
            className={`${styles.stepLabel} ${styles.serviceStepLabel}`}
          >
            STEP 3
          </p>

          <h2 className={styles.cardTitle}>
            What services do you offer?
          </h2>

          <p className={styles.cardText}>
            Add each service customers should
            be able to book. We&apos;ll connect
            them to staff in the next step.
          </p>
        </div>
      </div>

      <Message message={message} />

      <form
        className={
          styles.addServiceCard
        }
        onSubmit={addService}
      >
        <label
          className={styles.formLabel}
          htmlFor="serviceName"
        >
          Service name
        </label>

        <div className={styles.addRow}>
          <input
            id="serviceName"
            type="text"
            value={newServiceName}

            onChange={(event) =>
              setNewServiceName(
                event.target.value
              )
            }

            placeholder="Example: Haircut"
            className={styles.textInput}
            disabled={addingService}
          />

          <button
            type="submit"
            disabled={addingService}
            className={
              styles.serviceAddButton
            }
          >
            {addingService
              ? "Adding..."
              : "+ Add Service"}
          </button>
        </div>

        <div
          className={
            styles.serviceExamples
          }
        >
          Examples: Haircut, Color,
          Manicure, Massage, Personal
          Training
        </div>
      </form>

      <div
        className={styles.serviceList}
      >
        {services.length === 0 ? (
          <div
            className={styles.emptyState}
          >
            <div
              className={
                styles.emptyIcon
              }
            >
              ✨
            </div>

            <strong>
              Add your first service
            </strong>

            <p>
              Start with the service customers
              book most often.
            </p>
          </div>
        ) : (
          services.map((service) => (
            <div
              key={service.id}
              className={
                styles.serviceRow
              }
            >
              <div
                className={
                  styles.serviceMark
                }
              >
                ✓
              </div>

              <div
                className={
                  styles.personInfo
                }
              >
                <strong>
                  {service.name}
                </strong>

                <span>
                  Duration and price come next
                </span>
              </div>

              <button
                type="button"
                onClick={() =>
                  removeService(
                    service
                  )
                }
                className={
                  styles.removeButton
                }
              >
                Remove
              </button>
            </div>
          ))
        )}
      </div>

      <div className={styles.footer}>
        <button
          type="button"
          onClick={goBack}
          className={styles.backButton}
        >
          ← Back
        </button>

        <div
          className={
            styles.footerRight
          }
        >
          <div>
            <strong>
              {services.length}{" "}
              {services.length === 1
                ? "service"
                : "services"}{" "}
              added
            </strong>

            <p>
              You can change these later.
            </p>
          </div>

          <button
            type="button"
            onClick={
              continueFromServices
            }
            className={
              styles.continueButton
            }
          >
            Continue to Schedules →
          </button>
        </div>
      </div>
    </section>
  );
}

function ScheduleStep({
  staff,
  services,
  currentStaffIndex,
  staffServiceForm,
  updateStaffService,
  staffHours,
  updateStaffHours,
  savingStaffSetup,
  saveCurrentStaffSetup,
  goBack,
  message,
}) {
  const person =
    staff[currentStaffIndex];

  if (!person) {
    return null;
  }

  const selectedCount =
    services.filter(
      (service) =>
        staffServiceForm[service.id]
          ?.selected
    ).length;

  return (
    <section
      className={`${styles.mainCard} ${styles.scheduleCard}`}
    >
      <div className={styles.cardHeading}>
        <div
          className={`${styles.icon} ${styles.scheduleIcon}`}
        >
          📅
        </div>

        <div>
          <p
            className={`${styles.stepLabel} ${styles.scheduleStepLabel}`}
          >
            STEP 4
          </p>

          <h2 className={styles.cardTitle}>
            Set up {person.name}
          </h2>

          <p className={styles.cardText}>
            Choose what {person.name} does,
            what each service costs, and when
            customers can book them.
          </p>
        </div>
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "16px",
          marginBottom: "20px",
          padding: "14px 16px",

          background:
            "linear-gradient(135deg, #eef2ff, #eff6ff)",

          border:
            "1px solid #c7d2fe",

          borderRadius: "14px",
        }}
      >
        <div>
          <strong
            style={{
              color: "#312e81",
              fontSize: "15px",
            }}
          >
            Staff member{" "}
            {currentStaffIndex + 1} of{" "}
            {staff.length}
          </strong>

          <p
            style={{
              margin: "4px 0 0",
              color: "#64748b",
              fontSize: "12px",
            }}
          >
            We&apos;ll do one person at a
            time to keep setup simple.
          </p>
        </div>

        <div
          style={{
            minWidth: "42px",
            height: "42px",

            display: "flex",
            alignItems: "center",
            justifyContent: "center",

            color: "#ffffff",
            fontWeight: "900",

            background:
              "linear-gradient(135deg, #4f46e5, #2563eb)",

            borderRadius: "50%",
          }}
        >
          {String(person.name)
            .trim()
            .slice(0, 1)
            .toUpperCase()}
        </div>
      </div>

      <Message message={message} />

      <div
        style={{
          marginBottom: "26px",
        }}
      >
        <div
          style={{
            marginBottom: "12px",
          }}
        >
          <strong
            style={{
              color: "#1e293b",
              fontSize: "18px",
            }}
          >
            Services
          </strong>

          <p
            style={{
              margin: "5px 0 0",
              color: "#64748b",
              fontSize: "13px",
            }}
          >
            Select every service{" "}
            {person.name} performs, then enter
            the normal duration and price.
          </p>
        </div>

        <div
          style={{
            display: "grid",
            gap: "11px",
          }}
        >
          {services.map((service) => {
            const form =
              staffServiceForm[
                service.id
              ] || {
                selected: false,
                duration: "30",
                price: "",
              };

            return (
              <div
                key={service.id}

                style={{
                  padding: "16px",

                  background: form.selected
                    ? "#f5f3ff"
                    : "#f8fafc",

                  border: form.selected
                    ? "1px solid #c4b5fd"
                    : "1px solid #e2e8f0",

                  borderRadius: "14px",
                }}
              >
                <label
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                    cursor: "pointer",
                  }}
                >
                  <input
                    type="checkbox"

                    checked={
                      form.selected
                    }

                    onChange={(event) =>
                      updateStaffService(
                        service.id,
                        "selected",
                        event.target.checked
                      )
                    }

                    style={{
                      width: "18px",
                      height: "18px",
                    }}
                  />

                  <strong
                    style={{
                      color: "#1e293b",
                      fontSize: "15px",
                    }}
                  >
                    {service.name}
                  </strong>
                </label>

                {form.selected && (
                  <div
                    style={{
                      display: "grid",

                      gridTemplateColumns:
                        "1fr 1fr",

                      gap: "12px",
                      marginTop: "14px",
                    }}
                  >
                    <label>
                      <span
                        style={{
                          display: "block",

                          marginBottom:
                            "6px",

                          color: "#475569",

                          fontSize: "12px",
                          fontWeight: "800",
                        }}
                      >
                        Duration (minutes)
                      </span>

                      <input
                        type="number"
                        min="1"
                        step="1"

                        value={
                          form.duration
                        }

                        onChange={(event) =>
                          updateStaffService(
                            service.id,
                            "duration",
                            event.target.value
                          )
                        }

                        style={{
                          width: "100%",
                          minHeight: "44px",

                          padding:
                            "10px 12px",

                          border:
                            "1px solid #cbd5e1",

                          borderRadius:
                            "10px",

                          fontSize: "15px",
                        }}
                      />
                    </label>

                    <label>
                      <span
                        style={{
                          display: "block",

                          marginBottom:
                            "6px",

                          color: "#475569",

                          fontSize: "12px",
                          fontWeight: "800",
                        }}
                      >
                        Price ($)
                      </span>

                      <input
                        type="number"
                        min="0"
                        step="0.01"

                        value={
                          form.price
                        }

                        onChange={(event) =>
                          updateStaffService(
                            service.id,
                            "price",
                            event.target.value
                          )
                        }

                        placeholder="35"

                        style={{
                          width: "100%",
                          minHeight: "44px",

                          padding:
                            "10px 12px",

                          border:
                            "1px solid #cbd5e1",

                          borderRadius:
                            "10px",

                          fontSize: "15px",
                        }}
                      />
                    </label>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <p
          style={{
            margin: "10px 0 0",
            color: "#64748b",
            fontSize: "12px",
          }}
        >
          {selectedCount}{" "}
          {selectedCount === 1
            ? "service"
            : "services"}{" "}
          selected for {person.name}.
        </p>
      </div>

      <div>
        <div
          style={{
            marginBottom: "12px",
          }}
        >
          <strong
            style={{
              color: "#1e293b",
              fontSize: "18px",
            }}
          >
            Working hours
          </strong>

          <p
            style={{
              margin: "5px 0 0",
              color: "#64748b",
              fontSize: "13px",
            }}
          >
            We started with your normal shop
            hours. Change only what is
            different for {person.name}.
          </p>
        </div>

        <div className={styles.days}>
          {staffHours.map((day) => (
            <div
              key={day.weekday}

              className={`${styles.dayCard} ${
                day.open
                  ? styles.dayOpen
                  : styles.dayClosed
              }`}
            >
              <div
                className={styles.dayTop}
              >
                <div>
                  <strong
                    className={
                      styles.dayName
                    }
                  >
                    {day.name}
                  </strong>

                  <p
                    className={
                      day.open
                        ? styles.openText
                        : styles.closedText
                    }
                  >
                    {day.open
                      ? "Working"
                      : "Off"}
                  </p>
                </div>

                <label
                  className={styles.switch}
                >
                  <input
                    type="checkbox"

                    checked={day.open}

                    onChange={(event) =>
                      updateStaffHours(
                        day.weekday,
                        "open",
                        event.target.checked
                      )
                    }
                  />

                  <span
                    className={
                      styles.slider
                    }
                  />
                </label>
              </div>

              {day.open ? (
                <div
                  className={
                    styles.timeGrid
                  }
                >
                  <label>
                    <span>Starts</span>

                    <input
                      type="time"

                      value={day.start}

                      onChange={(event) =>
                        updateStaffHours(
                          day.weekday,
                          "start",
                          event.target.value
                        )
                      }
                    />
                  </label>

                  <label>
                    <span>Ends</span>

                    <input
                      type="time"

                      value={day.end}

                      onChange={(event) =>
                        updateStaffHours(
                          day.weekday,
                          "end",
                          event.target.value
                        )
                      }
                    />
                  </label>
                </div>
              ) : (
                <div
                  className={
                    styles.closedMessage
                  }
                >
                  {person.name} will not be
                  bookable on {day.name}.
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className={styles.footer}>
        <button
          type="button"
          onClick={goBack}
          disabled={savingStaffSetup}
          className={styles.backButton}
        >
          ← Back
        </button>

        <button
          type="button"

          onClick={
            saveCurrentStaffSetup
          }

          disabled={savingStaffSetup}

          className={
            styles.continueButton
          }
        >
          {savingStaffSetup
            ? "Saving..."
            : currentStaffIndex <
                staff.length - 1
              ? `Save ${person.name} & Continue →`
              : "Save & Continue to Payments →"}
        </button>
      </div>
    </section>
  );
}

function PaymentsStep({
  paymentPolicy,
  setPaymentPolicy,
  savingPaymentPolicy,
  connectStatus,
  loadingConnectStatus,
  connectStatusError,
  refreshConnectStatus,
  savePaymentPreference,
  goBack,
  message,
}) {
  const [startingConnect, setStartingConnect] =
    useState(false);

  const [
    connectActionError,
    setConnectActionError,
  ] = useState("");

  async function startStripeSetup() {
    if (
      startingConnect ||
      savingPaymentPolicy
    ) {
      return;
    }

    setStartingConnect(true);
    setConnectActionError("");

    try {
      const saved =
        await savePaymentPreference(false);

      if (!saved) {
        return;
      }

      const response = await fetch(
        "/api/billing/connect/start",
        {
          method: "POST",
          headers: {
            Accept: "application/json",
          },
        }
      );

      const data = await response
        .json()
        .catch(() => ({}));

      if (response.status === 401) {
        throw new Error(
          "Your login has expired. Please sign in again."
        );
      }

      if (!response.ok) {
        throw new Error(
          data.error ||
            data.detail ||
            "Could not start Stripe setup."
        );
      }

      if (!data.onboarding_url) {
        throw new Error(
          "Stripe did not return a setup link."
        );
      }

      window.location.href =
        data.onboarding_url;
    } catch (error) {
      console.error(error);

      setConnectActionError(
        error instanceof Error
          ? error.message
          : "Could not start Stripe setup."
      );
    } finally {
      setStartingConnect(false);
    }
  }

  const options = [
    {
      value: "none",
      icon: "📅",
      title: "No credit cards",
      description:
        "Customers can book appointments without providing a credit card.",
      note:
        "You can turn card payments on later from your Admin settings.",
      background:
        "linear-gradient(135deg, #f8fafc, #f1f5f9)",
      border: "#cbd5e1",
      selectedBorder: "#64748b",
    },
    {
      value: "accept_cards",
      icon: "💳",
      title: "Accept credit cards",
      description:
        "Accept card payments from customers for your services.",
      note:
        "We'll help you connect your payment account before card payments go live.",
      background:
        "linear-gradient(135deg, #eff6ff, #eef2ff)",
      border: "#bfdbfe",
      selectedBorder: "#2563eb",
    },
    {
      value: "card_required",
      icon: "🛡️",
      title: "Require a card to reserve",
      description:
        "Ask customers for a card when they book to help protect against no-shows.",
      note:
        "The customer is not automatically charged just for making the reservation.",
      background:
        "linear-gradient(135deg, #f5f3ff, #faf5ff)",
      border: "#ddd6fe",
      selectedBorder: "#7c3aed",
    },
  ];

  const hasConnectedAccount =
    Boolean(
      connectStatus
        ?.connected_account_exists
    );

  const detailsSubmitted =
    Boolean(
      connectStatus?.details_submitted
    );

  const chargesEnabled =
    Boolean(
      connectStatus?.charges_enabled
    );

  const payoutsEnabled =
    Boolean(
      connectStatus?.payouts_enabled
    );

  const paymentAccountReady =
    hasConnectedAccount &&
    detailsSubmitted &&
    chargesEnabled &&
    payoutsEnabled;

  const paymentAccountInReview =
    hasConnectedAccount &&
    detailsSubmitted &&
    !paymentAccountReady;

  function renderConnectStatus() {
    if (paymentPolicy === "none") {
      return null;
    }

    if (loadingConnectStatus) {
      return (
        <div
          style={{
            marginTop: "18px",
            padding: "14px 16px",
            color: "#475569",
            fontSize: "13px",
            lineHeight: "1.5",
            background: "#f8fafc",
            border:
              "1px solid #e2e8f0",
            borderRadius: "13px",
          }}
        >
          Checking your payment
          account...
        </div>
      );
    }

    if (connectStatusError) {
      return (
        <div
          style={{
            marginTop: "18px",
            padding: "14px 16px",
            color: "#991b1b",
            fontSize: "13px",
            lineHeight: "1.5",
            background: "#fef2f2",
            border:
              "1px solid #fecaca",
            borderRadius: "13px",
          }}
        >
          <strong>
            We could not check your
            payment account.
          </strong>{" "}
          {connectStatusError}

          <div
            style={{
              marginTop: "10px",
            }}
          >
            <button
              type="button"
              onClick={
                refreshConnectStatus
              }
              style={{
                padding: "8px 12px",
                color: "#991b1b",
                fontWeight: "800",
                background: "#ffffff",
                border:
                  "1px solid #fecaca",
                borderRadius: "9px",
                cursor: "pointer",
              }}
            >
              Try Again
            </button>
          </div>
        </div>
      );
    }

    if (paymentAccountReady) {
      return (
        <div
          style={{
            marginTop: "18px",
            padding: "14px 16px",
            color: "#047857",
            fontSize: "13px",
            lineHeight: "1.5",
            background:
              "linear-gradient(135deg, #ecfdf5, #f0fdf4)",
            border:
              "1px solid #a7f3d0",
            borderRadius: "13px",
          }}
        >
          <strong>
            Payment account connected ✓
          </strong>{" "}
          Your Stripe account is ready
          to accept customer card
          payments and receive payouts.
        </div>
      );
    }

    if (paymentAccountInReview) {
      return (
        <div
          style={{
            marginTop: "18px",
            padding: "14px 16px",
            color: "#92400e",
            fontSize: "13px",
            lineHeight: "1.5",
            background:
              "linear-gradient(135deg, #fffbeb, #fefce8)",
            border:
              "1px solid #fde68a",
            borderRadius: "13px",
          }}
        >
          <strong>
            Payment account submitted —
            verification in progress.
          </strong>{" "}
          Stripe has your information.
          Card payments and payouts will
          become available after Stripe
          finishes its review.

          <div
            style={{
              marginTop: "10px",
            }}
          >
            <button
              type="button"
              onClick={
                refreshConnectStatus
              }
              style={{
                padding: "8px 12px",
                color: "#92400e",
                fontWeight: "800",
                background: "#ffffff",
                border:
                  "1px solid #fde68a",
                borderRadius: "9px",
                cursor: "pointer",
              }}
            >
              Check Again
            </button>
          </div>
        </div>
      );
    }

    return (
      <div
        style={{
          marginTop: "18px",
          padding: "14px 16px",
          color: "#1e40af",
          fontSize: "13px",
          lineHeight: "1.5",
          background:
            "linear-gradient(135deg, #eff6ff, #eef2ff)",
          border:
            "1px solid #bfdbfe",
          borderRadius: "13px",
        }}
      >
        <strong>
          Payment account setup is
          required.
        </strong>{" "}
        Connect your business to Stripe
        before customers can use credit
        cards.
      </div>
    );
  }

  return (
    <section
      className={`${styles.mainCard} ${styles.scheduleCard}`}
    >
      <div
        className={styles.cardHeading}
      >
        <div
          className={styles.icon}
          style={{
            background:
              "linear-gradient(135deg, #dbeafe, #ede9fe)",
          }}
        >
          💳
        </div>

        <div>
          <p
            className={
              styles.stepLabel
            }
            style={{
              color: "#4f46e5",
            }}
          >
            STEP 5
          </p>

          <h2
            className={
              styles.cardTitle
            }
          >
            Do you want to accept
            credit cards?
          </h2>

          <p
            className={
              styles.cardText
            }
          >
            This is optional. Choose
            what works best for your
            business. You can change it
            later.
          </p>
        </div>
      </div>

      <Message message={message} />

      <div
        style={{
          display: "grid",
          gap: "14px",
        }}
      >
        {options.map((option) => {
          const selected =
            paymentPolicy ===
            option.value;

          return (
            <button
              key={option.value}
              type="button"
              onClick={() =>
                setPaymentPolicy(
                  option.value
                )
              }
              disabled={
                savingPaymentPolicy
              }
              style={{
                width: "100%",
                padding: "18px",
                textAlign: "left",
                background:
                  option.background,
                border: selected
                  ? `3px solid ${option.selectedBorder}`
                  : `1px solid ${option.border}`,
                borderRadius: "16px",
                cursor:
                  savingPaymentPolicy
                    ? "default"
                    : "pointer",
                boxShadow: selected
                  ? "0 4px 14px rgba(15, 23, 42, 0.08)"
                  : "none",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems:
                    "flex-start",
                  gap: "14px",
                }}
              >
                <div
                  style={{
                    width: "46px",
                    height: "46px",
                    flexShrink: 0,
                    display: "flex",
                    alignItems:
                      "center",
                    justifyContent:
                      "center",
                    fontSize: "23px",
                    background:
                      "#ffffff",
                    border:
                      `1px solid ${option.border}`,
                    borderRadius:
                      "12px",
                  }}
                >
                  {option.icon}
                </div>

                <div
                  style={{
                    flex: 1,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems:
                        "center",
                      justifyContent:
                        "space-between",
                      gap: "12px",
                    }}
                  >
                    <strong
                      style={{
                        color:
                          "#0f172a",
                        fontSize:
                          "17px",
                      }}
                    >
                      {option.title}
                    </strong>

                    <span
                      style={{
                        width: "24px",
                        height: "24px",
                        flexShrink: 0,
                        display: "flex",
                        alignItems:
                          "center",
                        justifyContent:
                          "center",
                        color: selected
                          ? "#ffffff"
                          : "#94a3b8",
                        fontSize:
                          "13px",
                        fontWeight:
                          "900",
                        background:
                          selected
                            ? option.selectedBorder
                            : "#ffffff",
                        border:
                          `2px solid ${
                            selected
                              ? option.selectedBorder
                              : "#cbd5e1"
                          }`,
                        borderRadius:
                          "50%",
                      }}
                    >
                      {selected
                        ? "✓"
                        : ""}
                    </span>
                  </div>

                  <p
                    style={{
                      margin:
                        "6px 0 0",
                      color:
                        "#475569",
                      fontSize:
                        "14px",
                      lineHeight:
                        "1.5",
                    }}
                  >
                    {
                      option.description
                    }
                  </p>

                  <p
                    style={{
                      margin:
                        "7px 0 0",
                      color:
                        "#64748b",
                      fontSize:
                        "12px",
                      lineHeight:
                        "1.45",
                    }}
                  >
                    {option.note}
                  </p>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {renderConnectStatus()}

      {connectActionError && (
        <div
          style={{
            marginTop: "14px",
            padding: "12px 14px",
            color: "#991b1b",
            fontSize: "13px",
            lineHeight: "1.5",
            background: "#fef2f2",
            border: "1px solid #fecaca",
            borderRadius: "12px",
          }}
        >
          {connectActionError}
        </div>
      )}

      <div
        className={styles.footer}
      >
        <button
          type="button"
          onClick={goBack}
          disabled={
            savingPaymentPolicy ||
            startingConnect
          }
          className={
            styles.backButton
          }
        >
          ← Back
        </button>

        <button
          type="button"
          onClick={() => {
            if (
              paymentPolicy !== "none" &&
              !detailsSubmitted
            ) {
              startStripeSetup();
              return;
            }

            savePaymentPreference();
          }}
          disabled={
            savingPaymentPolicy ||
            startingConnect ||
            loadingConnectStatus
          }
          className={
            styles.continueButton
          }
        >
          {startingConnect
            ? "Opening Stripe..."
            : savingPaymentPolicy
              ? "Saving..."
              : loadingConnectStatus &&
                  paymentPolicy !== "none"
                ? "Checking Stripe..."
                : paymentPolicy !== "none" &&
                    !detailsSubmitted
                  ? hasConnectedAccount
                    ? "Continue Stripe Setup →"
                    : "Connect Stripe to Continue →"
                  : "Save & Continue to Review →"}
        </button>
      </div>
    </section>
  );
}

function ReviewStep({
  shopSlug,
  staff,
  services,
  assignedServices,
  openBookingPage,
  finishOnboarding,
  goBack,
}) {
  return (
    <section
      className={`${styles.mainCard} ${styles.scheduleCard}`}
    >
      <div className={styles.cardHeading}>
        <div
          className={styles.icon}
          style={{
            background:
              "linear-gradient(135deg, #d1fae5, #dcfce7)",
          }}
        >
          🎉
        </div>

        <div>
          <p
            className={styles.stepLabel}
            style={{
              color: "#047857",
            }}
          >
            STEP 6
          </p>

          <h2 className={styles.cardTitle}>
            You&apos;re ready to take
            appointments
          </h2>

          <p className={styles.cardText}>
            Review the basics below, then
            open your booking page and make
            sure everything looks right.
          </p>
        </div>
      </div>

      <div
        style={{
          display: "grid",

          gridTemplateColumns:
            "repeat(2, minmax(0, 1fr))",

          gap: "12px",
          marginBottom: "22px",
        }}
      >
        <SummaryBox
          value={staff.length}
          label={
            staff.length === 1
              ? "Staff member"
              : "Staff members"
          }
        />

        <SummaryBox
          value={services.length}
          label={
            services.length === 1
              ? "Service"
              : "Services"
          }
        />
      </div>

      <div
        style={{
          padding: "20px",

          background:
            "linear-gradient(135deg, #ecfdf5, #f0fdf4)",

          border:
            "1px solid #a7f3d0",

          borderRadius: "16px",
        }}
      >
        <strong
          style={{
            display: "block",
            color: "#065f46",
            fontSize: "16px",
          }}
        >
          Your public booking page
        </strong>

        <p
          style={{
            margin: "7px 0 0",
            color: "#047857",
            fontSize: "14px",
            wordBreak: "break-word",
          }}
        >
          www.chairtimehq.com/{shopSlug}
        </p>

        <button
          type="button"
          onClick={openBookingPage}
          style={{
            marginTop: "14px",
            minHeight: "46px",

            padding: "11px 18px",

            color: "#ffffff",

            fontSize: "14px",
            fontWeight: "900",

            background: "#059669",

            border: "none",
            borderRadius: "10px",

            cursor: "pointer",
          }}
        >
          Open My Booking Page ↗
        </button>
      </div>

      <div className={styles.footer}>
        <button
          type="button"
          onClick={goBack}
          className={styles.backButton}
        >
          ← Back
        </button>

        <button
          type="button"
          onClick={finishOnboarding}
          className={
            styles.continueButton
          }
        >
          Finish Setup & Go to Admin →
        </button>
      </div>
    </section>
  );
}

function SummaryBox({
  value,
  label,
}) {
  return (
    <div
      style={{
        padding: "18px",
        textAlign: "center",

        background: "#f8fafc",

        border:
          "1px solid #e2e8f0",

        borderRadius: "14px",
      }}
    >
      <strong
        style={{
          display: "block",

          color: "#1e293b",

          fontSize: "26px",
        }}
      >
        {value}
      </strong>

      <span
        style={{
          display: "block",

          marginTop: "3px",

          color: "#64748b",

          fontSize: "12px",
        }}
      >
        {label}
      </span>
    </div>
  );
}

function Message({
  message,
}) {
  if (!message) return null;

  return (
    <div className={styles.message}>
      {message}
    </div>
  );
}
