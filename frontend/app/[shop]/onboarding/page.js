Warning: truncated output (original token count: 34281)
Total output lines: 5541

"use client";
 
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useParams, useRouter } from "next/navigation";
import styles from "./onboarding.module.css";
import OwnerVoicemailSetup from "./OwnerVoicemailSetup";
 
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
 
  const [aiOnly, setAiOnly] = useState(false);
  const [aiUpgradeVerified, setAiUpgradeVerified] = useState(false);
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
 
  const [aiVoiceEnabled, setAiVoiceEnabled] =
    useState(false);
 
  // Step 6 stays open until the shop reviews and saves live-transfer preferences.
  const [staffTransferReady, setStaffTransferReady] = useState(false);
 
  const [aiProvisionStatus, setAiProvisionStatus] =
    useState(null);
 
  const [
    loadingAiProvisionStatus,
    setLoadingAiProvisionStatus,
  ] = useState(false);
 
  const [
    aiProvisionStatusError,
    setAiProvisionStatusError,
  ] = useState("");
 
  const [provisioningAi, setProvisioningAi] =
    useState(false);
 
  // AI Receptionist phone-number chooser.
  // Selection is intentionally temporary at this stage.
  // Nothing here purchases, assigns, routes, or saves a number.
  const [aiAreaCode, setAiAreaCode] =
    useState("");
 
  const [
    availableAiNumbers,
    setAvailableAiNumbers,
  ] = useState([]);
 
  const [aiSearchFingerprint, setAiSearchFingerprint] =
    useState("");
 
  const [
    loadingAiNumbers,
    setLoadingAiNumbers,
  ] = useState(false);
 
  const [aiNumberError, setAiNumberError] =
    useState("");
 
  const [
    selectedAiNumber,
    setSelectedAiNumber,
  ] = useState("");
 
  const [
    recoveryAiNumber,
    setRecoveryAiNumber,
  ] = useState("");
 
  const [
    activatingAiNumber,
    setActivatingAiNumber,
  ] = useState(false);
 
  const totalSteps = aiVoiceEnabled ? 7 : 6;
  const reviewStep = aiVoiceEnabled ? 7 : 6;
 
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
 
  const loadAiProvisionStatus = useCallback(
    async () => {
      if (!shopSlug || !aiVoiceEnabled) {
        setAiProvisionStatus(null);
        setAiProvisionStatusError("");
        return;
      }
 
      setLoadingAiProvisionStatus(true);
      setAiProvisionStatusError("");
 
      try {
        const response = await fetch(
          "/api/ai-setup/provision/status",
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
              "Could not check your AI Receptionist setup."
          );
        }
 
        if (data.chairtime_shop?.slug !== shopSlug) {
          throw new Error("Please sign in to this shop’s account before continuing AI setup.");
        }
        setAiProvisionStatus(data);
      } catch (error) {
        console.error(error);
 
        setAiProvisionStatusError(
          error instanceof Error
            ? error.message
            : "Could not check your AI Receptionist setup."
        );
      } finally {
        setLoadingAiProvisionStatus(false);
      }
    },
    [aiVoiceEnabled, router, shopSlug]
  );
 
  async function provisionAiReceptionist() {
    if (provisioningAi || !aiVoiceEnabled) return;
 
    setProvisioningAi(true);
    setAiProvisionStatusError("");
    setMessage("");
 
    try {
      const response = await fetch(
        "/api/ai-setup/provision",
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
        router.replace(
          `/login?next=${encodeURIComponent(
            `/${shopSlug}/onboarding`
          )}`
        );
        return;
      }
 
      if (!response.ok) {
        const detail =
          typeof data.detail === "string"
            ? data.detail
            : data.detail?.message;
 
        throw new Error(
          data.error ||
            detail ||
            "Could not set up your AI Receptionist."
        );
      }
 
      await loadAiProvisionStatus();
      setMessage("Your AI Receptionist is ready.");
    } catch (error) {
      console.error(error);
 
      setAiProvisionStatusError(
        error instanceof Error
          ? error.message
          : "Could not set up your AI Receptionist."
      );
    } finally {
      setProvisioningAi(false);
    }
  }
 
  async function loadAvailableAiNumbers() {
    if (loadingAiNumbers || activatingAiNumber) return;
 
    const cleanAreaCode = String(
      aiAreaCode || ""
    ).replace(/\D/g, "");
 
    if (cleanAreaCode.length !== 3) {
      setAiNumberError(
        "Enter a valid 3-digit area code."
      );
      setAvailableAiNumbers([]);
      setAiSearchFingerprint("");
      setSelectedAiNumber("");
      return;
    }
 
    setLoadingAiNumbers(true);
    setAiNumberError("");
    setAvailableAiNumbers([]);
    setAiSearchFingerprint("");
    setSelectedAiNumber("");
    setRecoveryAiNumber("");
 
    try {
      const response = await fetch(
        `/api/ai-setup/phone-numbers/available?area_code=${encodeURIComponent(
          cleanAreaCode
        )}`,
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
        const detail =
          typeof data.detail === "string"
            ? data.detail
            : data.detail?.message;
 
        throw new Error(
          data.error ||
            detail ||
            "Could not find available phone numbers."
        );
      }
 
      const numbers = Array.isArray(
        data.available_numbers
      )
        ? data.available_numbers
        : [];
 
      setAvailableAiNumbers(numbers);
      setAiSearchFingerprint(
        String(data.fingerprint_id || "").trim()
      );
 
      if (numbers.length === 0) {
        setAiNumberError(
          `No available numbers were found for area code ${cleanAreaCode}. Try another nearby area code.`
        );
      }
    } catch (error) {
      console.error(error);
 
      setAvailableAiNumbers([]);
 
      setAiNumberError(
        error instanceof Error
          ? error.message
          : "Could not find available phone numbers."
      );
    } finally {
      setLoadingAiNumbers(false);
    }
  }
 
  async function activateAiNumberAndContinue() {
    if (activatingAiNumber || loadingAiNumbers) return;
 
    const activePhoneNumber =
      aiProvisionStatus?.phone_number ||
      aiProvisionStatus?.agent?.inbound_number ||
      "";
 
    if (activePhoneNumber) {
      setMessage("");
      // Do not skip the staff-transfer choice for an existing AI number.
      // The button is disabled until the choice has been saved.
      if (staffTransferReady && !aiOnly) goToStep(7);
      return;
    }
 
    const recoveryDigits = String(
      recoveryAiNumber || ""
    ).replace(/\D/g, "");
 
    const recoveryPhoneNumber =
      recoveryDigits.length === 10
        ? `+1${recoveryDigits}`
        : recoveryDigits.length === 11 &&
            recoveryDigits.startsWith("1")
          ? `+${recoveryDigits}`
          : "";
 
    const phoneNumberToActivate =
      selectedAiNumber || recoveryPhoneNumber;
 
    if (!phoneNumberToActivate) {
      setAiNumberError(
        recoveryDigits.length > 0
          ? "Enter a valid 10-digit AI Receptionist phone number."
          : "Choose an AI Receptionist phone number before continuing."
      );
      return;
    }
 
    const selectedRecord = availableAiNumbers.find(
      (number) => number.phone_number === selectedAiNumber
    );
 
    if (selectedAiNumber && (
      !aiSearchFingerprint ||
      !selectedRecord?.locality ||
      !selectedRecord?.region
    )) {
      setAiNumberError(
        "Please find numbers again and select a number with complete purchase information."
      );
      return;
    }
 
    setActivatingAiNumber(true);
    setAiNumberError("");
    setMessage("");
 
    try {
      const response = await fetch(
        "/api/ai-setup/phone-number/purchase",
        {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            phone_number: phoneNumberToActivate,
            ...(selectedAiNumber ? {
              fingerprint_id: aiSearchFingerprint,
              locality: selectedRecord.locality,
              region: selectedRecord.region,
            } : {}),
          }),
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
        const detail =
          typeof data.detail === "string"
            ? data.detail
            : data.detail?.message;
 
        throw new Error(
          data.error ||
            detail ||
            "Could not activate your AI Receptionist phone number."
        );
      }
 
      if (!data.success || !data.phone_number) {
        throw new Error(
          "DayTello could not verify your AI Receptionist phone number."
        );
      }
 
      await loadAiProvisionStatus();
      setSelectedAiNumber(data.phone_number);
      setStaffTransferReady(false);
      // Keep the owner on Step 6 to choose live-transfer preferences.
      setMessage("Your AI number is active. Choose how to handle requests for an employee below.");
    } catch (error) {
      console.error(error);
 
      setAiNumberError(
        error instanceof Error
          ? error.message
          : "Could not activate your AI Receptionist phone number."
      );
    } finally {
      setActivatingAiNumber(false);
    }
  }
 
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
 
  useEffect(() => {
    if (
      !shopSlug ||
      !aiVoiceEnabled ||
      currentStep !== 6
    ) {
      return;
    }
 
    loadAiProvisionStatus();
  }, [
    aiVoiceEnabled,
    currentStep,
    loadAiProvisionStatus,
    shopSlug,
  ]);
 
  async function loadOnboardingData() {
    const aiSetupOnly = new URLSearchParams(window.location.search).get("setup") === "ai";
    setAiOnly(aiSetupOnly);
    setAiUpgradeVerified(false);
    try {
      if (aiSetupOnly) {
        const response = await fetch("/api/account/ai-upgrade", { cache: "no-store" });
        const verified = await response.json();
        if (response.status === 401) {
          router.replace(`/login?next=${encodeURIComponent(`/${shopSlug}/onboarding?setup=ai`)}`);
          return;
        }
        if (!response.ok) throw new Error(typeof verified.detail === "string" ? verified.detail : "Could not verify your AI plan.");
        if (verified.shop_slug !== shopSlug || !verified.already_upgraded) throw new Error("Confirm the AI upgrade in this shop’s Account Options first.");
      }
      const [
        hoursResponse,
        staffResponse,
        servicesResponse,
        assignedServicesResponse,
        availabilityResponse,
        shopResponse,
      ] = await Promise.all([
        fetch(
          `/api/shops/${encodeURIComponent(
            shopSlug
          )}/shop-availability-rules`,
          {
            cache: "no-store",
          }
        ),
        fetch(
          `/api/shops/${encodeURIComponent(
            shopSlug
          )}/barbers`,
          {
            cache: "no-store",
          }
        ),
        fetch(
          `/api/shops/${encodeURIComponent(
            shopSlug
          )}/service-catalog`,
          {
            cache: "no-store",
          }
        ),
        fetch(
          `/api/shops/${encodeURIComponent(
            shopSlug
          )}/services`,
          {
            cache: "no-store",
          }
        ),
        fetch(
          `/api/shops/${encodeURIComponent(
            shopSlug
          )}/availability-rules`,
          {
            cache: "no-store",
          }
        ),
        fetch(
          `/api/shops/${encodeURIComponent(
            shopSlug
          )}`,
          {
            cache: "no-store",
          }
        ),
      ]);
 
      if (
        hoursResponse.status === 401 ||
        staffResponse.status === 401 ||
        servicesResponse.status === 401 ||
        assignedServicesResponse.status === 401 ||
        availabilityResponse.status === 401 ||
        shopResponse.status === 401
      ) {
        router.replace(
          `/login?next=${encodeURIComponent(
            `/${shopSlug}/onboarding`
          )}`
        );
 
        return;
      }
 
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
        Array.isArray(shopData)
          ? shopData[0] || null
          : shopData?.shop || shopData || null;
 
      if (currentShop?.slug !== shopSlug) throw new Error("The saved shop does not match this setup page.");
      setPaymentPolicy(
        currentShop?.payment_policy || "none"
      );
 
      setAiVoiceEnabled(
        Boolean(currentShop?.ai_voice_enabled)
      );
 
      setExistingRules(
        Array.isArray(hoursData)
          ? hoursData
          : []
      );
 
      setStaff(
        Array.isArray(staffData)
          ? staffData
          : []
      );
 
      setServices(
        Array.isArray(servicesData)
          ? servicesData
          : []
      );
 
      setAssignedServices(
        Array.isArray(assignedServicesData)
          ? assignedServicesData
          : []
      );
 
      setAvailabilityRules(
        Array.isArray(availabilityData)
          ? availabilityData
          : []
      );
 
      const safeHoursData =
        Array.isArray(hoursData)
          ? hoursData
          : [];
 
      const safeStaffData =
        Array.isArray(staffData)
          ? staffData
          : [];
 
      const safeServicesData =
        Array.isArray(servicesData)
          ? servicesData
          : [];
 
      const safeAssignedServicesData =
        Array.isArray(assignedServicesData)
          ? assignedServicesData
          : [];
 
      const safeAvailabilityData =
        Array.isArray(availabilityData)
          ? availabilityData
          : [];
 
      const normalizedHours =
        safeHoursData.length > 0
          ? DAYS.map((day) => {
              const rule =
                safeHoursData.find(
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
 
      if (aiSetupOnly) {
        if (!currentShop?.ai_voice_enabled) throw new Error("Your AI subscription is not yet verified. Check Account Options again.");
        if (!safeHoursData.length || !safeStaffData.length || !safeAssignedServicesData.some((service) => service.is_active !== false) || !safeAvailabilityData.length) {
          throw new Error("Complete your shop services, staff and hours before setting up AI.");
        }
        setAiUpgradeVerified(true);
        setCurrentStep(6);
      } else if (safeHoursData.length === 0) {
        setCurrentStep(1);
      } else if (safeStaffData.length === 0) {
        setCurrentStep(2);
      } else if (safeServicesData.length === 0) {
        setCurrentStep(3);
      } else {
        const firstIncompleteIndex =
          safeStaffData.findIndex(
            (person) => {
              const hasService =
                safeAssignedServicesData.some(
                  (service) =>
                    service.barber_id ===
                    person.id
                );
 
              const hasHours =
                safeAvailabilityData.some(
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
            safeStaffData[firstIncompleteIndex],
            safeServicesData,
            safeAssignedServicesData,
            safeAvailabilityData,
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
            service.barber_id === person.id &&
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
          existing?.duration_minutes ?? ""
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
          `/api/shops/${encodeURIComponent(
            shopSlug
          )}/shop-availability-rules/${encodeURIComponent(
            rule.id
          )}`,
          {
            method: "DELETE",
          }
        );
 
        if (deleteResponse.status === 401) {
          router.replace(
            `/login?next=${encodeURIComponent(
              `/${shopSlug}/onboarding`
            )}`
          );
 
          return;
        }
 
        if (!deleteResponse.ok) {
          throw new Error(
            "Could not update your shop hours."
          );
        }
      }
 
      for (const day of hours) {
        if (!day.open) continue;
 
        const response = await fetch(
          `/api/shops/${encodeURIComponent(
            shopSlug
          )}/shop-availability-rules`,
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
 
        if (response.status === 401) {
          router.replace(
            `/login?next=${encodeURIComponent(
              `/${shopSlug}/onboarding`
            )}`
          );
 
          return;
        }
 
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
          `/api/shops/${encodeURIComponent(
            shopSlug
          )}/shop-availability-rules`,
          {
            cache: "no-store",
          }
        );
 
      if (refreshedResponse.status === 401) {
        router.replace(
          `/login?next=${encodeURIComponent(
            `/${shopSlug}/onboarding`
          )}`
        );
 
        return;
      }
 
      if (refreshedResponse.ok) {
        const refreshedData =
          await refreshedResponse.json();
 
        setExistingRules(
          Array.isArray(refreshedData)
            ? refreshedData
            : []
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
        `/api/shops/${encodeURIComponent(
          shopSlug
        )}/barbers`,
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
 
      if (response.status === 401) {
        router.replace(
          `/login?next=${encodeURIComponent(
            `/${shopSlug}/onboarding`
          )}`
        );
 
        return;
      }
 
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
      `/api/shops/${encodeURIComponent(
        shopSlug
      )}/barbers`,
      {
        cache: "no-store",
      }
    );
 
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
        "Could not reload your staff."
      );
    }
 
    const staffData =
      await response.json();
 
    setStaff(
      Array.isArray(staffData)
        ? staffData
        : []
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
        `/api/shops/${encodeURIComponent(
          shopSlug
        )}/barbers/${encodeURIComponent(
          person.id
        )}`,
        {
          method: "DELETE",
        }
      );
 
      if (response.status === 401) {
        router.replace(
          `/login?next=${encodeURIComponent(
            `/${shopSlug}/onboarding`
          )}`
        );
 
        return;
      }
 
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
        `/api/shops/${encodeURIComponent(
          shopSlug
        )}/service-catalog`,
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
 
      if (response.status === 401) {
        router.replace(
          `/login?next=${encodeURIComponent(
            `/${shopSlug}/onboarding`
          )}`
        );
 
        return;
      }
 
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
      `/api/shops/${encodeURIComponent(
        shopSlug
      )}/service-catalog`,
      {
        cache: "no-store",
      }
    );
 
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
        "Could not reload your services."
      );
    }
 
    const servicesData =
      await response.json();
 
    setServices(
      Array.isArray(servicesData)
        ? servicesData
        : []
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
        `/api/shops/${encodeURIComponent(
          shopSlug
        )}/service-catalog/${encodeURIComponent(
          service.id
        )}`,
        {
          method: "DELETE",
        }
      );
 
      if (response.status === 401) {
        router.replace(
          `/login?next=${encodeURIComponent(
            `/${shopSlug}/onboarding`
          )}`
        );
 
        return;
      }
 
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
    const [
      servicesResponse,
      availabilityResponse,
    ] = await Promise.all([
      fetch(
        `/api/shops/${encodeURIComponent(
          shopSlug
        )}/services`,
        {
          cache: "no-store",
        }
      ),
 
      fetch(
        `/api/shops/${encodeURIComponent(
          shopSlug
        )}/availability-rules`,
        {
          cache: "no-store",
        }
      ),
    ]);
 
    if (
      servicesResponse.status === 401 ||
      availabilityResponse.status === 401
    ) {
      router.replace(
        `/login?next=${encodeURIComponent(
          `/${shopSlug}/onboarding`
        )}`
      );
 
      throw new Error(
        "Your session has expired."
      );
    }
 
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
 
    const safeAssignedServices =
      Array.isArray(nextAssignedServices)
        ? nextAssignedServices
        : [];
 
    const safeAvailabilityRules =
      Array.isArray(nextAvailabilityRules)
        ? nextAvailabilityRules
        : [];
 
    setAssignedServices(
      safeAssignedServices
    );
 
    setAvailabilityRules(
      safeAvailabilityRules
    );
 
    return {
      nextAssignedServices:
        safeAssignedServices,
 
      nextAvailabilityRules:
        safeAvailabilityRules,
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
            duration: "",
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
                `/api/shops/${encodeURIComponent(
                  shopSlug
                )}/services/${encodeURIComponent(
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
                `Could not update ${catalogService.name} for ${person.name}.`
              );
            }
          } else {
            const response =
              await fetch(
                `/api/shops/${encodeURIComponent(
                  shopSlug
                )}/services`,
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
 
            if (response.status === 401) {
              router.replace(
                `/login?next=${encodeURIComponent(
                  `/${shopSlug}/onboarding`
                )}`
              );
 
              return;
            }
 
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
              `/api/shops/${encodeURIComponent(
                shopSlug
              )}/services/${encodeURIComponent(
                existing.id
              )}`,
              {
                method: "DELETE",
              }
            );
 
          if (response.status === 401) {
            router.replace(
              `/login?next=${encodeURIC…12281 tokens truncated…n (
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
                    {option.description}
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
            border:
              "1px solid #fecaca",
            borderRadius: "12px",
          }}
        >
          {connectActionError}
        </div>
      )}
 
      <div className={styles.footer}>
        <button
          type="button"
          onClick={goBack}
          disabled={
            savingPaymentPolicy ||
            startingConnect
          }
          className={styles.backButton}
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
 
function AiReceptionistStep({
  aiOnly = false,
  shopSlug,
  finishSetup,
  provisionStatus,
  staffTransferReady,
  onStaffTransferReadyChange,
  loadingStatus,
  statusError,
  provisioning,
  provisionAiReceptionist,
  refreshStatus,
  goBack,
  continueToReview,
  activatingAiNumber,
  aiAreaCode,
  setAiAreaCode,
  availableAiNumbers,
  loadingAiNumbers,
  aiNumberError,
  selectedAiNumber,
  setSelectedAiNumber,
  recoveryAiNumber,
  setRecoveryAiNumber,
  loadAvailableAiNumbers,
  message,
}) {
  const [voicemailRelayReady, setVoicemailRelayReady] = useState(false);
  const handleVoicemailRelayReady = useCallback((ready) => {
    setVoicemailRelayReady(ready);
    onStaffTransferReadyChange(ready);
  }, [onStaffTransferReadyChange]);

  const provisioned = Boolean(
    provisionStatus?.provisioned
  );
 
  const activePhoneNumber =
    provisionStatus?.phone_number ||
    provisionStatus?.agent?.inbound_number ||
    "";
 
  const agentName =
    provisionStatus?.agent?.agent_name ||
    provisionStatus?.agent?.name ||
    "Your AI Receptionist";
 
  return (
    <section
      className={`${styles.mainCard} ${styles.scheduleCard}`}
    >
      <div className={styles.cardHeading}>
        <div
          className={styles.icon}
          style={{
            background:
              "linear-gradient(135deg, #ede9fe, #e0e7ff)",
          }}
        >
          ☎️
        </div>
 
        <div>
          <p
            className={styles.stepLabel}
            style={{ color: "#6d28d9" }}
          >
            {aiOnly ? "AI SETUP" : "STEP 6"}
          </p>
 
          <h2 className={styles.cardTitle}>
            Set up your AI Receptionist
          </h2>
 
          <p className={styles.cardText}>
            Your plan includes an AI receptionist that can
            answer calls, check your real DayTello
            availability, and book appointments for you.
          </p>
        </div>
      </div>
 
      {provisioning ? (
        <div className={styles.message} role="status">
          <strong>Setting up your AI Receptionist…</strong>
          <div>This can take a moment. Keep this page open while we finish.</div>
        </div>
      ) : (
        <Message message={message} />
      )}
 
      <div
        style={{
          padding: "20px",
          background: provisioned
            ? "linear-gradient(135deg, #ecfdf5, #f0fdf4)"
            : "linear-gradient(135deg, #f5f3ff, #eef2ff)",
          border: provisioned
            ? "1px solid #a7f3d0"
            : "1px solid #c4b5fd",
          borderRadius: "16px",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: "14px",
          }}
        >
          <div
            style={{
              width: "46px",
              height: "46px",
              flexShrink: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "22px",
              background: "#ffffff",
              border: provisioned
                ? "1px solid #a7f3d0"
                : "1px solid #c4b5fd",
              borderRadius: "12px",
            }}
          >
            {provisioned ? "✓" : "🤖"}
          </div>
 
          <div style={{ flex: 1 }}>
            <strong
              style={{
                display: "block",
                color: provisioned
                  ? "#065f46"
                  : "#312e81",
                fontSize: "17px",
              }}
            >
              {loadingStatus
                ? "Checking your AI setup..."
                : provisioned
                  ? `${agentName} is ready`
                  : "Ready to create your AI Receptionist"}
            </strong>
 
            <p
              style={{
                margin: "7px 0 0",
                color: provisioned
                  ? "#047857"
                  : "#4f46e5",
                fontSize: "14px",
                lineHeight: "1.55",
              }}
            >
              {provisioned
                ? "Your dedicated AI receptionist is connected to your real availability, services, staff, and booking actions."
                : "DayTello will create a dedicated AI receptionist for this business."}
            </p>
 
          </div>
        </div>
      </div>
 
      {!provisioned && !loadingStatus && (
        <div
          style={{
            marginTop: "16px",
            padding: "16px",
            background: "#f8fafc",
            border: "1px solid #e2e8f0",
            borderRadius: "14px",
          }}
        >
          <strong
            style={{
              display: "block",
              color: "#0f172a",
              fontSize: "14px",
            }}
          >
            What happens next
          </strong>
 
          <p
            style={{
              margin: "6px 0 0",
              color: "#64748b",
              fontSize: "13px",
              lineHeight: "1.55",
            }}
          >
            We&apos;ll create your receptionist using this shop&apos;s saved services, staff, prices and schedules.
          </p>
        </div>
      )}
 
      {provisioned && !activePhoneNumber && (
        <div
          style={{
            marginTop: "18px",
            padding: "20px",
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            borderRadius: "16px",
          }}
        >
          <div>
            <strong
              style={{
                display: "block",
                color: "#0f172a",
                fontSize: "17px",
              }}
            >
              Choose your local phone number
            </strong>
 
            <p
              style={{
                margin: "6px 0 0",
                color: "#64748b",
                fontSize: "14px",
                lineHeight: "1.55",
              }}
            >
              Enter the area code you want customers to see
              when they call your AI receptionist.
            </p>
          </div>
 
          <div
            style={{
              display: "flex",
              gap: "10px",
              alignItems: "flex-end",
              marginTop: "16px",
              flexWrap: "wrap",
            }}
          >
            <label
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "6px",
              }}
            >
              <span
                style={{
                  fontSize: "13px",
                  fontWeight: 700,
                  color: "#334155",
                }}
              >
                Area code
              </span>
 
              <input
                type="text"
                inputMode="numeric"
                value={aiAreaCode}
                maxLength={3}
                onChange={(event) =>
                  setAiAreaCode(event.target.value)
                }
                onKeyDown={(event) => {
                  if (
                    event.key === "Enter" &&
                    aiAreaCode.length === 3
                  ) {
                    event.preventDefault();
                    loadAvailableAiNumbers();
                  }
                }}
                disabled={
                  loadingAiNumbers ||
                  activatingAiNumber
                }
                style={{
                  width: "130px",
                  padding: "11px 12px",
                  border: "1px solid #cbd5e1",
                  borderRadius: "10px",
                  fontSize: "16px",
                  outline: "none",
                }}
              />
            </label>
 
            <button
              type="button"
              onClick={loadAvailableAiNumbers}
              disabled={
                loadingAiNumbers ||
                activatingAiNumber ||
                aiAreaCode.length !== 3
              }
              className={styles.continueButton}
            >
              {loadingAiNumbers
                ? "Searching..."
                : "Find Numbers"}
            </button>
          </div>
 
          {aiNumberError && (
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
              {aiNumberError}
            </div>
          )}
 
          {availableAiNumbers.length > 0 && (
            <div
              style={{
                display: "grid",
                gap: "9px",
                marginTop: "16px",
              }}
            >
              {availableAiNumbers.map((number) => {
                const selected =
                  selectedAiNumber ===
                  number.phone_number;
 
                const place = [
                  number.locality,
                  number.region &&
                  number.region !== "US"
                    ? number.region
                    : null,
                ]
                  .filter(Boolean)
                  .join(", ");
 
                return (
                  <label
                    key={number.phone_number}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "12px",
                      padding: "13px 14px",
                      border: selected
                        ? "2px solid #6d28d9"
                        : "1px solid #e2e8f0",
                      borderRadius: "12px",
                      background: selected
                        ? "#f5f3ff"
                        : "#ffffff",
                      cursor: "pointer",
                    }}
                  >
                    <input
                      type="radio"
                      name="aiPhoneNumber"
                      value={number.phone_number}
                      checked={selected}
                      disabled={activatingAiNumber}
                      onChange={() => {
                        setSelectedAiNumber(
                          number.phone_number
                        );
                        setRecoveryAiNumber("");
                      }}
                    />
 
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: "2px",
                      }}
                    >
                      <strong
                        style={{
                          color: "#0f172a",
                          fontSize: "15px",
                        }}
                      >
                        {number.friendly_name ||
                          number.phone_number}
                      </strong>
 
                      {place && (
                        <span
                          style={{
                            color: "#64748b",
                            fontSize: "13px",
                          }}
                        >
                          {place}
                        </span>
                      )}
                    </div>
                  </label>
                );
              })}
            </div>
          )}
 
          <div
            style={{
              marginTop: "18px",
              paddingTop: "18px",
              borderTop: "1px solid #e2e8f0",
            }}
          >
            <strong
              style={{
                display: "block",
                color: "#0f172a",
                fontSize: "14px",
              }}
            >
              Already purchased a DayTello AI number?
            </strong>
 
            <p
              style={{
                margin: "6px 0 10px",
                color: "#64748b",
                fontSize: "13px",
                lineHeight: "1.5",
              }}
            >
              If DayTello previously purchased a number for
              this business but setup was interrupted, enter
              that exact number here. DayTello will reconnect
              the owned number instead of purchasing it again.
            </p>
 
            <input
              type="tel"
              inputMode="tel"
              value={recoveryAiNumber}
              placeholder="2025550123"
              onChange={(event) => {
                const digits = String(
                  event.target.value || ""
                )
                  .replace(/\D/g, "")
                  .slice(0, 11);
 
                setRecoveryAiNumber(digits);
                setSelectedAiNumber("");
                setAiNumberError("");
              }}
              disabled={activatingAiNumber}
              style={{
                width: "220px",
                maxWidth: "100%",
                padding: "11px 12px",
                border: "1px solid #cbd5e1",
                borderRadius: "10px",
                fontSize: "16px",
                outline: "none",
              }}
            />
          </div>
 
          {recoveryAiNumber && (
            <div
              style={{
                marginTop: "14px",
                padding: "12px 14px",
                background: "#eff6ff",
                border: "1px solid #bfdbfe",
                borderRadius: "12px",
                color: "#1e40af",
                fontSize: "14px",
                fontWeight: 700,
              }}
            >
              DayTello will verify this number is already
              owned before activating it.
            </div>
          )}
 
          {selectedAiNumber && (
            <div
              style={{
                marginTop: "14px",
                padding: "12px 14px",
                background: "#ecfdf5",
                border: "1px solid #a7f3d0",
                borderRadius: "12px",
                color: "#065f46",
                fontSize: "14px",
                fontWeight: 700,
              }}
            >
              ✓ Number selected. DayTello will verify the
              number before purchasing or activating it.
            </div>
          )}
 
          {activatingAiNumber && (
            <div
              style={{
                marginTop: "14px",
                padding: "12px 14px",
                background: "#f8fafc",
                border: "1px solid #cbd5e1",
                borderRadius: "12px",
                color: "#334155",
                fontSize: "14px",
                fontWeight: 700,
              }}
            >
              Activating your AI Receptionist phone number.
              Please do not leave this page.
            </div>
          )}
        </div>
      )}
 
      {activePhoneNumber ? (
        <AiPhoneForwardingHelp
          aiPhoneNumber={activePhoneNumber}
          shopSlug={shopSlug}
          phoneRouted={provisionStatus?.phone_routed}
          refreshStatus={refreshStatus}
          loadingStatus={loadingStatus}
        />
      ) : null}
 
      {activePhoneNumber && provisioned ? (
        <OwnerVoicemailSetup
          key={shopSlug}
          shopSlug={shopSlug}
          onReadyChange={handleVoicemailRelayReady}
        />
      ) : null}

      {activePhoneNumber && provisioned && !voicemailRelayReady ? (
        <AiStaffTransferSetup
          key={`${shopSlug}-${activePhoneNumber}`}
          shopSlug={shopSlug}
          aiPhoneNumber={activePhoneNumber}
          onReadyChange={onStaffTransferReadyChange}
        />
      ) : null}
 
      {statusError && (
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
          {statusError}
        </div>
      )}
 
      <div className={styles.footer}>
        <button
          type="button"
          onClick={goBack}
          disabled={
            provisioning || activatingAiNumber
          }
          className={styles.backButton}
        >
          ← Back
        </button>
 
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            flexWrap: "wrap",
            justifyContent: "flex-end",
          }}
        >
          {statusError && (
            <button
              type="button"
              onClick={refreshStatus}
              disabled={
                loadingStatus || provisioning
              }
              className={styles.backButton}
            >
              {loadingStatus
                ? "Checking..."
                : "Check Again"}
            </button>
          )}
 
          {!provisioned ? (
            <button
              type="button"
              onClick={provisionAiReceptionist}
              disabled={
                loadingStatus || provisioning
              }
              className={styles.continueButton}
            >
              {provisioning
                ? "Setting Up AI Receptionist..."
                : loadingStatus
                  ? "Checking Setup..."
                  : "Set Up AI Receptionist →"}
            </button>
          ) : (
            <button
              type="button"
              onClick={aiOnly && activePhoneNumber ? finishSetup : continueToReview}
              disabled={
                activatingAiNumber ||
                (Boolean(activePhoneNumber) && !staffTransferReady) ||
                (aiOnly && activePhoneNumber && !provisionStatus?.phone_routed) ||
                (!activePhoneNumber &&
                  !selectedAiNumber &&
                  String(recoveryAiNumber || "")
                    .replace(/\D/g, "")
                    .length < 10)
              }
              className={styles.continueButton}
            >
              {activatingAiNumber
                ? "Activating Phone Number..."
                : activePhoneNumber
                  ? (aiOnly ? "Finish AI Setup →" : "Continue to Review →")
                  : (aiOnly ? "Activate Receptionist Number →" : "Activate Number & Continue →")}
            </button>
          )}
        </div>
      </div>
    </section>
  );
}
 
// AI Receptionist live-human transfers are configured per shop's HighLevel agent.
// The backend is authoritative. Nothing is considered saved until it reads back
// the actual HighLevel CALL_TRANSFER action for this shop.
function AiStaffTransferSetup({ shopSlug, aiPhoneNumber, onReadyChange }) {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [choice, setChoice] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [loopConfirmed, setLoopConfirmed] = useState(false);
  const [otherTransferDetected, setOtherTransferDetected] = useState(false);
  const [error, setError] = useState("");
  const [savedMessage, setSavedMessage] = useState("");
 
  useEffect(() => {
    let canceled = false;
    onReadyChange(false);
    setLoading(true);
    setError("");
    setSavedMessage("");
    setChoice("");
    setPhoneNumber("");
    setLoopConfirmed(false);
 
    async function load() {
      try {
        const response = await fetch("/api/ai-setup/staff-transfer", {
          headers: { Accept: "application/json" },
          cache: "no-store",
        });
        const data = await response.json().catch(() => ({}));
        if (canceled) return;
        if (response.status === 401) {
          router.replace(`/login?next=${encodeURIComponent(`/${shopSlug}/onboarding`)}`);
          return;
        }
        if (!response.ok) {
          throw new Error(typeof data.detail === "string"
            ? data.detail : "Could not load the call-transfer setting.");
        }
        if (data.provisioned !== true || data.shop_slug !== shopSlug) {
          throw new Error("The AI Receptionist transfer setting does not match this shop.");
        }
        const conflict = Boolean(data.other_transfer_actions_detected);
        setOtherTransferDetected(conflict);
        setPhoneNumber(data.phone_number || "");
        if (data.enabled) {
          setChoice("yes");
          // Existing transfer already saved to the shop's agent.
          onReadyChange(!conflict);
          if (!conflict) setSavedMessage("Live transfers are already configured for this shop.");
        } else {
          // An absent HighLevel action means transfers are off. Ask the owner
          // to explicitly choose No or Yes before finishing setup.
          setChoice("");
          onReadyChange(false);
        }
        if (conflict) {
          setError("Another transfer action exists on this shop's AI agent. " +
            "Please contact DayTello support to review it before continuing.");
        }
      } catch (err) {
        if (!canceled) {
          onReadyChange(false);
          setError(err instanceof Error ? err.message : "Could not load transfer settings.");
        }
      } finally {
        if (!canceled) setLoading(false);
      }
    }
    load();
    return () => { canceled = true; };
  }, [shopSlug, aiPhoneNumber, onReadyChange, router]);
 
  function changeChoice(next) {
    setChoice(next);
    setError("");
    setSavedMessage("");
    onReadyChange(false);
  }
 
  function changePhone(next) {
    setPhoneNumber(next);
    setError("");
    setSavedMessage("");
    onReadyChange(false);
  }
 
  async function save() {
    if (loading || saving || otherTransferDetected) return;
    if (choice !== "yes" && choice !== "no") {
      setError("Choose whether calls should transfer to a live person.");
      return;
    }
    const digits = phoneNumber.replace(/\D/g, "");
    if (choice === "yes" && !(digits.length === 10 ||
      (digits.length === 11 && digits.startsWith("1")))) {
      setError("Enter a valid 10-digit US or Canadian telephone number.");
      return;
    }
    if (choice === "yes" && !loopConfirmed) {
      setError("Please confirm the transfer number will not forward back to AI.");
      return;
    }
    setSaving(true);
    setError("");
    setSavedMessage("");
    onReadyChange(false);
    try {
      const response = await fetch("/api/ai-setup/staff-transfer", {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        body: JSON.stringify({
          enabled: choice === "yes",
          phone_number: choice === "yes" ? phoneNumber.trim() : null,
          confirm_no_forwarding_loop: choice === "yes" ? loopConfirmed : false,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (response.status === 401) {
        router.replace(`/login?next=${encodeURIComponent(`/${shopSlug}/onboarding`)}`);
        return;
      }
      if (!response.ok) {
        const detail = typeof data.detail === "string" ? data.detail :
          (typeof data.detail?.message === "string" ? data.detail.message :
            "Could not save the transfer setting. Please try again.");
        throw new Error(detail);
      }
      if (data.shop_slug !== shopSlug || data.enabled !== (choice === "yes") ||
        data.other_transfer_actions_detected) {
        throw new Error("The saved transfer setting could not be verified for this shop.");
      }
      if (choice === "yes") {
        const cleaned = `+${digits.length === 10 ? `1${digits}` : digits}`;
        if (data.phone_number !== cleaned) {
          throw new Error("The transfer destination could not be verified.");
        }
        setPhoneNumber(data.phone_number);
        setSavedMessage("Saved for this AI receptionist. Test a real call before relying on transfers.");
      } else {
        setPhoneNumber("");
        setSavedMessage("Saved: customer calls will not be transferred to an employee.");
      }
      onReadyChange(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save call transfers.");
      onReadyChange(false);
    } finally {
      setSaving(false);
    }
  }
 
  const choiceDisabled = loading || saving || otherTransferDetected;
  const radioRow = { display: "flex", alignItems: "flex-start", gap: "10px",
    padding: "10px 12px", background: "#fff", border: "1px solid #e2e8f0",
    borderRadius: "10px", cursor: choiceDisabled ? "not-allowed" : "pointer" };
  return (
    <section aria-label="Choose how calls reach an employee" style={{
      marginTop: "20px", padding: "20px", border: "1px solid #c4b5fd",
      borderRadius: "16px", background: "#faf5ff",
    }}>
      <h3 style={{ margin: 0, color: "#312e81", fontSize: "20px", fontWeight: 800 }}>
        When a caller asks to speak to an employee
      </h3>
      <p style={{ color: "#4338ca", fontSize: "14px", lineHeight: 1.6 }}>
        Would you like DayTello to transfer these calls to a live phone number?
        You can choose not to be interrupted. No texting is required.
      </p>
      {loading ? (
        <p aria-live="polite">Loading your call-transfer setting...</p>
      ) : (
        <div style={{ display: "grid", gap: "10px" }}>
          <label style={radioRow}>
            <input type="radio" name="daytelloStaffTransfer" value="no"
              checked={choice === "no"} disabled={choiceDisabled}
              onChange={() => changeChoice("no")} />
            <span><strong>No — do not transfer calls.</strong><br />
              The AI receptionist will continue handling appointment and shop questions.</span>
          </label>
          <label style={radioRow}>
            <input type="radio" name="daytelloStaffTransfer" value="yes"
              checked={choice === "yes"} disabled={choiceDisabled}
              onChange={() => changeChoice("yes")} />
            <span><strong>Yes — try to connect callers to a live phone number.</strong><br />
              If unanswered, the destination phone may provide its usual voicemail.</span>
          </label>
          {choice === "yes" ? (
            <div style={{ padding: "10px 12px", background: "#fff", borderRadius: "10px" }}>
              <label htmlFor="daytelloTransferNumber" style={{ display: "block", fontWeight: 800 }}>
                Direct employee phone number
              </label>
              <input id="daytelloTransferNumber" type="tel" inputMode="tel"
                value={phoneNumber} onChange={(event) => changePhone(event.target.value)}
                disabled={choiceDisabled} placeholder="(555) 123-4567"
                style={{ width: "100%", maxWidth: "320px", marginTop: "8px",
                  padding: "12px", border: "1px solid #94a3b8", borderRadius: "9px" }} />
              <label style={{ display: "flex", gap: "8px", alignItems: "flex-start",
                marginTop: "12px", fontSize: "13px" }}>
                <input type="checkbox" checked={loopConfirmed}
                  disabled={choiceDisabled}
                  onChange={(event) => { setLoopConfirmed(event.target.checked);
                    onReadyChange(false); setSavedMessage(""); }} />
                I confirm this phone number does not forward back to my AI receptionist
                or to my business number if that number forwards to the AI.
              </label>
              <p style={{ fontSize: "12px", color: "#475569", lineHeight: 1.6 }}>
                Use a direct line, not your published business number or DayTello AI number.
                Test an answered call, an unanswered call, and voicemail afterward.
              </p>
            </div>
          ) : null}
          {error ? <p role="alert" style={{ color: "#991b1b", fontWeight: 700 }}>{error}</p> : null}
          {savedMessage ? <p role="status" style={{ color: "#166534", fontWeight: 700 }}>
            {savedMessage}</p> : null}
          <div>
            <button type="button" className={styles.continueButton}
              disabled={choiceDisabled || !choice}
              onClick={save}>
              {saving ? "Saving..." : "Save Call Transfer Choice"}
            </button>
          </div>
        </div>
      )}
      <p style={{ marginTop: "12px", color: "#64748b", fontSize: "12px", lineHeight: 1.5 }}>
        A live transfer needs a real telephone test before the shop relies on it.
        No two-way texting is included. Appointment texts are automated.
      </p>
    </section>
  );
}
 
function AiPhoneForwardingHelp({
  aiPhoneNumber,
  shopSlug,
  phoneRouted,
  refreshStatus,
  loadingStatus = false,
}) {
  if (!aiPhoneNumber) return null;
 
  return (
    <section
      aria-label="AI Receptionist phone forwarding instructions"
      style={{
        marginTop: "20px",
        padding: "20px",
        borderRadius: "16px",
        border: "1px solid #a7f3d0",
        background: "#f0fdf4",
      }}
    >
      <h3
        style={{
          fontSize: "20px",
          fontWeight: 800,
          color: "#065f46",
          margin: 0,
        }}
      >
        Your AI Receptionist phone number
      </h3>
 
      <a
        href={`tel:${aiPhoneNumber}`}
        style={{
          display: "inline-block",
          marginTop: "10px",
          color: "#065f46",
          fontSize: "22px",
          fontWeight: 800,
          overflowWrap: "anywhere",
        }}
      >
        {aiPhoneNumber}
      </a>
 
      <p style={{ marginTop: "10px", color: "#166534", lineHeight: 1.6 }}>
        You can give customers this number directly, or keep the business
        number they already know and forward calls to your AI Receptionist.
        Forwarding is optional.
      </p>
 
      <h4 style={{ marginTop: "18px", fontWeight: 800, color: "#065f46" }}>
        How to forward your existing business number
      </h4>
      <ol style={{ marginTop: "8px", paddingLeft: "22px", lineHeight: 1.75, color: "#166534" }}>
        <li>Call the new AI number above first to confirm it answers correctly.</li>
        <li>
          Open the call-forwarding settings with your existing phone provider.
          Choose to forward all calls, or only unanswered calls if your provider
          supports that option.
        </li>
        <li>Set the forwarding destination to your AI number shown above.</li>
        <li>
          Call your existing business number from another phone and confirm
          the AI Receptionist answers and can book an appointment.
        </li>
      </ol>
      <p style={{ marginTop: "10px", color: "#166534", fontSize: "13px", lineHeight: 1.6 }}>
        Your existing phone provider controls forwarding. Contact them for
        instructions specific to your plan. Avoid routing the AI back to the
        same business number you forward to it, which could cause a call loop.
      </p>
      <p style={{ marginTop: "10px", color: "#166534", fontSize: "13px", lineHeight: 1.6 }}>
        Your online booking page stays at <strong>daytello.com/{shopSlug}</strong>.
      </p>
 
      {phoneRouted === false && (
        <p role="alert" style={{ marginTop: "12px", color: "#92400e", fontWeight: 700 }}>
          DayTello has not yet verified that this number is routed to your AI
          Receptionist. Check again before forwarding your business calls.
        </p>
      )}
 
      {typeof refreshStatus === "function" && (
        <button
          type="button"
          onClick={refreshStatus}
          disabled={loadingStatus}
          className={styles.backButton}
          style={{ marginTop: "14px" }}
        >
          {loadingStatus ? "Checking..." : "Check AI Phone Connection"}
        </button>
      )}
    </section>
  );
}
 
function ReviewStep({
  shopSlug,
  aiPhoneNumber,
  aiPhoneRouted,
  staff,
  services,
  assignedServices,
  openBookingPage,
  finishOnboarding,
  goBack,
  stepNumber,
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
            STEP {stepNumber}
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
          www.daytello.com/{shopSlug}
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
 
      {aiPhoneNumber ? (
        <AiPhoneForwardingHelp
          aiPhoneNumber={aiPhoneNumber}
          shopSlug={shopSlug}
          phoneRouted={aiPhoneRouted}
        />
      ) : null}
 
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
          className={styles.continueButton}
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
