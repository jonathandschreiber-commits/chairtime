"use client";

import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useParams } from "next/navigation";

const API_BASE =
  "https://chairtime-production-94da.up.railway.app";

const STRIPE_PUBLISHABLE_KEY =
  process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY ||
  "";

let stripeScriptPromise = null;


function loadStripeScript() {
  if (
    typeof window !== "undefined" &&
    window.Stripe
  ) {
    return Promise.resolve();
  }

  if (stripeScriptPromise) {
    return stripeScriptPromise;
  }

  stripeScriptPromise = new Promise(
    (resolve, reject) => {
      const existingScript =
        document.querySelector(
          'script[src="https://js.stripe.com/v3/"]'
        );

      if (existingScript) {
        if (window.Stripe) {
          resolve();
          return;
        }

        existingScript.addEventListener(
          "load",
          () => resolve()
        );

        existingScript.addEventListener(
          "error",
          () =>
            reject(
              new Error(
                "Stripe could not be loaded."
              )
            )
        );

        return;
      }

      const script =
        document.createElement("script");

      script.src =
        "https://js.stripe.com/v3/";

      script.async = true;

      script.onload = () => resolve();

      script.onerror = () =>
        reject(
          new Error(
            "Stripe could not be loaded."
          )
        );

      document.head.appendChild(script);
    }
  );

  return stripeScriptPromise;
}


function cleanPhone(phone) {
  let digits = String(
    phone || ""
  ).replace(/\D/g, "");

  if (
    digits.length === 11 &&
    digits.startsWith("1")
  ) {
    digits = digits.slice(1);
  }

  return digits;
}


function cardBrandLabel(brand) {
  const value = String(
    brand || ""
  ).toLowerCase();

  if (value === "visa") {
    return "Visa";
  }

  if (value === "mastercard") {
    return "Mastercard";
  }

  if (value === "amex") {
    return "American Express";
  }

  if (value === "discover") {
    return "Discover";
  }

  return brand
    ? String(brand)
    : "Card";
}


export default function ShopBookingPage() {
  const params = useParams();

  const SHOP_SLUG = Array.isArray(
    params?.shop
  )
    ? params.shop[0]
    : params?.shop || "";

  const today = new Date()
    .toISOString()
    .slice(0, 10);

  const [shopName, setShopName] =
    useState("");

  const [
    paymentPolicy,
    setPaymentPolicy,
  ] = useState("none");

  const [barbers, setBarbers] =
    useState([]);

  const [services, setServices] =
    useState([]);

  const [
    availableSlots,
    setAvailableSlots,
  ] = useState([]);

  const [
    customerName,
    setCustomerName,
  ] = useState("");

  const [
    customerPhone,
    setCustomerPhone,
  ] = useState("");

  const [notes, setNotes] =
    useState("");

  const [
    selectedBarberId,
    setSelectedBarberId,
  ] = useState("");

  const [
    selectedServiceId,
    setSelectedServiceId,
  ] = useState("");

  const [
    selectedDate,
    setSelectedDate,
  ] = useState(today);

  const [
    selectedSlot,
    setSelectedSlot,
  ] = useState("");

  const [message, setMessage] =
    useState("");

  const [booking, setBooking] =
    useState(false);

  const [
    preparingCard,
    setPreparingCard,
  ] = useState(false);

  const [
    cardFormReady,
    setCardFormReady,
  ] = useState(false);

  const [
    cardElementReady,
    setCardElementReady,
  ] = useState(false);

  const [
    cardComplete,
    setCardComplete,
  ] = useState(false);

  const [cardError, setCardError] =
    useState("");

  const [
    verificationStatus,
    setVerificationStatus,
  ] = useState("idle");

  const [
    verificationCode,
    setVerificationCode,
  ] = useState("");

  const [
    verificationToken,
    setVerificationToken,
  ] = useState("");

  const [
    verificationMessage,
    setVerificationMessage,
  ] = useState("");

  const [
    verifiedCustomer,
    setVerifiedCustomer,
  ] = useState(null);

  const [
    savedCard,
    setSavedCard,
  ] = useState(null);

  const [
    useSavedCard,
    setUseSavedCard,
  ] = useState(true);

  const stripeRef = useRef(null);

  const elementsRef = useRef(null);

  const cardElementRef =
    useRef(null);

  const cardElementContainerRef =
    useRef(null);

  const setupIntentClientSecretRef =
    useRef(null);


  async function loadData() {
    if (!SHOP_SLUG) {
      return;
    }

    try {
      const query =
        `?shop_slug=${encodeURIComponent(
          SHOP_SLUG
        )}`;

      const [
        shopRes,
        barbersRes,
        servicesRes,
      ] = await Promise.all([
        fetch(
          `${API_BASE}/api/shops${query}`
        ),

        fetch(
          `${API_BASE}/api/barbers${query}`
        ),

        fetch(
          `${API_BASE}/api/services${query}`
        ),
      ]);

      if (shopRes.ok) {
        const shops =
          await shopRes.json();

        if (
          Array.isArray(shops) &&
          shops.length > 0
        ) {
          const shop = shops[0];

          if (shop?.name) {
            setShopName(shop.name);
          }

          setPaymentPolicy(
            shop?.payment_policy ||
              "none"
          );
        }
      }

      if (barbersRes.ok) {
        setBarbers(
          await barbersRes.json()
        );
      }

      if (servicesRes.ok) {
        setServices(
          await servicesRes.json()
        );
      }
    } catch (error) {
      console.error(
        "Could not load booking data:",
        error
      );
    }
  }


  useEffect(() => {
    loadData();
  }, [SHOP_SLUG]);


  const availableServices =
    useMemo(() => {
      if (!selectedBarberId) {
        return [];
      }

      return services.filter(
        (service) =>
          service.barber_id ===
          selectedBarberId
      );
    }, [
      services,
      selectedBarberId,
    ]);


  const selectedService =
    useMemo(() => {
      return (
        services.find(
          (service) =>
            service.id ===
            selectedServiceId
        ) || null
      );
    }, [
      services,
      selectedServiceId,
    ]);


  useEffect(() => {
    if (
      !SHOP_SLUG ||
      !selectedBarberId ||
      !selectedServiceId ||
      !selectedDate
    ) {
      setAvailableSlots([]);
      setSelectedSlot("");
      return;
    }

    async function loadAvailability() {
      setSelectedSlot("");

      try {
        const searchParams =
          new URLSearchParams({
            shop_slug: SHOP_SLUG,

            barber_id:
              selectedBarberId,

            service_id:
              selectedServiceId,

            target_date:
              selectedDate,
          });

        const response =
          await fetch(
            `${API_BASE}/api/availability?${searchParams.toString()}`
          );

        if (!response.ok) {
          setAvailableSlots([]);
          return;
        }

        const data =
          await response.json();

        setAvailableSlots(
          data.slots || []
        );
      } catch (error) {
        console.error(
          "Could not load availability:",
          error
        );

        setAvailableSlots([]);
      }
    }

    loadAvailability();
  }, [
    SHOP_SLUG,
    selectedBarberId,
    selectedServiceId,
    selectedDate,
  ]);


  useEffect(() => {
    resetCardForm();
  }, [
    selectedBarberId,
    selectedServiceId,
    selectedDate,
    selectedSlot,
  ]);


  useEffect(() => {
    if (
      !cardFormReady ||
      !cardElementRef.current ||
      !cardElementContainerRef.current
    ) {
      return;
    }

    try {
      cardElementRef.current.mount(
        cardElementContainerRef.current
      );
    } catch (error) {
      console.error(
        "Could not mount Stripe card entry:",
        error
      );

      setCardError(
        "Secure card entry could not be opened. Please try again."
      );
    }
  }, [cardFormReady]);


  function formatTime(value) {
    return new Date(
      value
    ).toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit",
    });
  }


  function resetCardForm() {
    try {
      if (cardElementRef.current) {
        cardElementRef.current.destroy();
      }
    } catch {
      // Nothing else is needed here.
    }

    cardElementRef.current = null;
    elementsRef.current = null;
    stripeRef.current = null;

    setupIntentClientSecretRef.current =
      null;

    setCardFormReady(false);
    setCardElementReady(false);
    setCardComplete(false);
    setCardError("");
  }


  function resetVerification({
    clearCustomer = false,
  } = {}) {
    setVerificationStatus("idle");
    setVerificationCode("");
    setVerificationToken("");
    setVerificationMessage("");
    setVerifiedCustomer(null);
    setSavedCard(null);
    setUseSavedCard(true);

    if (clearCustomer) {
      setCustomerName("");
    }

    resetCardForm();
  }


  function handlePhoneChange(event) {
    const newPhone =
      event.target.value;

    const oldCleanPhone =
      cleanPhone(customerPhone);

    const newCleanPhone =
      cleanPhone(newPhone);

    setCustomerPhone(newPhone);

    if (
      oldCleanPhone !==
        newCleanPhone &&
      verificationStatus !== "idle"
    ) {
      resetVerification({
        clearCustomer:
          Boolean(verifiedCustomer),
      });
    }
  }


  async function requestVerification() {
    const phone =
      cleanPhone(customerPhone);

    if (phone.length !== 10) {
      setVerificationMessage(
        "Please enter a valid 10-digit phone number."
      );

      return {
        verificationRequired: false,
        newCustomer: false,
      };
    }

    if (
      verificationStatus ===
      "requesting"
    ) {
      return {
        verificationRequired: false,
        newCustomer: false,
      };
    }

    setVerificationStatus(
      "requesting"
    );

    setVerificationMessage("");
    setMessage("");

    try {
      const response = await fetch(
        `${API_BASE}/api/customer-verification/request`,
        {
          method: "POST",

          headers: {
            "Content-Type":
              "application/json",
          },

          body: JSON.stringify({
            shop_slug: SHOP_SLUG,
            customer_phone:
              customerPhone.trim(),
          }),
        }
      );

      const data = await response
        .json()
        .catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          typeof data.detail ===
            "string"
            ? data.detail
            : "We couldn't verify this phone number."
        );
      }

      if (
        data.verification_required
      ) {
        setVerificationStatus(
          "code_sent"
        );

        setVerificationMessage(
          "We texted you a 6-digit verification code."
        );

        return {
          verificationRequired: true,
          newCustomer: false,
        };
      }

      setVerificationStatus(
        "new_customer"
      );

      setVerificationMessage(
        ""
      );

      return {
        verificationRequired: false,
        newCustomer: true,
      };
    } catch (error) {
      console.error(
        "Could not request customer verification:",
        error
      );

      setVerificationStatus("idle");

      setVerificationMessage(
        error instanceof Error
          ? error.message
          : "We couldn't send the verification code."
      );

      return {
        verificationRequired: false,
        newCustomer: false,
      };
    }
  }


  async function confirmVerification() {
    const phone =
      cleanPhone(customerPhone);

    const code =
      verificationCode
        .replace(/\D/g, "")
        .slice(0, 6);

    if (phone.length !== 10) {
      setVerificationMessage(
        "Please enter a valid 10-digit phone number."
      );
      return;
    }

    if (code.length !== 6) {
      setVerificationMessage(
        "Please enter the 6-digit code we texted you."
      );
      return;
    }

    if (
      verificationStatus ===
      "verifying"
    ) {
      return;
    }

    setVerificationStatus(
      "verifying"
    );

    setVerificationMessage("");

    try {
      const response = await fetch(
        `${API_BASE}/api/customer-verification/confirm`,
        {
          method: "POST",

          headers: {
            "Content-Type":
              "application/json",
          },

          body: JSON.stringify({
            shop_slug: SHOP_SLUG,
            customer_phone:
              customerPhone.trim(),
            code,
          }),
        }
      );

      const data = await response
        .json()
        .catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          typeof data.detail ===
            "string"
            ? data.detail
            : "The verification code could not be confirmed."
        );
      }

      if (
        !data.verified ||
        !data.verification_token
      ) {
        throw new Error(
          "Phone verification could not be completed."
        );
      }

      setVerificationToken(
        data.verification_token
      );

      setVerificationStatus(
        "verified"
      );

      setVerificationCode("");

      setVerifiedCustomer(
        data.customer || null
      );

      setSavedCard(
        data.saved_card || null
      );

      setUseSavedCard(
        Boolean(data.saved_card)
      );

      if (data.customer?.name) {
        setCustomerName(
          data.customer.name
        );
      }

      if (
        data.customer
          ?.last_barber_id &&
        barbers.some(
          (barber) =>
            barber.id ===
            data.customer.last_barber_id
        )
      ) {
        setSelectedBarberId(
          data.customer.last_barber_id
        );

        const priorServiceId =
          data.customer
            ?.last_service_id;

        const priorServiceValid =
          priorServiceId &&
          services.some(
            (service) =>
              service.id ===
                priorServiceId &&
              service.barber_id ===
                data.customer
                  .last_barber_id
          );

        setSelectedServiceId(
          priorServiceValid
            ? priorServiceId
            : ""
        );

        setSelectedSlot("");
      }

      setVerificationMessage("");
    } catch (error) {
      console.error(
        "Could not confirm customer verification:",
        error
      );

      setVerificationStatus(
        "code_sent"
      );

      setVerificationMessage(
        error instanceof Error
          ? error.message
          : "The verification code could not be confirmed."
      );
    }
  }


  async function prepareCardForm() {
    if (preparingCard) {
      return;
    }

    if (!validateBookingFields()) {
      return;
    }

    if (!STRIPE_PUBLISHABLE_KEY) {
      setCardError(
        "Secure card entry is not configured yet."
      );

      return;
    }

    resetCardForm();

    setPreparingCard(true);
    setMessage("");
    setCardError("");
    setCardComplete(false);
    setCardElementReady(false);

    try {
      const response = await fetch(
        `${API_BASE}/api/billing/booking/setup-intent`,
        {
          method: "POST",

          headers: {
            "Content-Type":
              "application/json",
          },

          body: JSON.stringify({
            shop_slug: SHOP_SLUG,

            customer_name:
              customerName.trim(),

            customer_phone:
              customerPhone.trim(),

            use_saved_card: false,
          }),
        }
      );

      const data = await response
        .json()
        .catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          typeof data.detail ===
            "string"
            ? data.detail
            : "Could not prepare secure card entry."
        );
      }

      if (
        !data.client_secret ||
        !data.stripe_connect_account_id
      ) {
        throw new Error(
          "Stripe did not return the information needed for secure card entry."
        );
      }

      await loadStripeScript();

      if (!window.Stripe) {
        throw new Error(
          "Stripe could not be loaded."
        );
      }

      const stripe =
        window.Stripe(
          STRIPE_PUBLISHABLE_KEY,
          {
            stripeAccount:
              data.stripe_connect_account_id,
          }
        );

      const elements =
        stripe.elements();

      const cardElement =
        elements.create("card", {
          hidePostalCode: false,

          style: {
            base: {
              fontSize: "16px",
              color: "#111827",

              "::placeholder": {
                color: "#9ca3af",
              },
            },

            invalid: {
              color: "#b91c1c",
            },
          },
        });

      stripeRef.current = stripe;

      elementsRef.current =
        elements;

      cardElementRef.current =
        cardElement;

      setupIntentClientSecretRef.current =
        data.client_secret;

      cardElement.on(
        "ready",
        () => {
          setCardElementReady(true);
        }
      );

      cardElement.on(
        "change",
        (event) => {
          setCardComplete(
            Boolean(event.complete)
          );

          if (event.error) {
            setCardError(
              event.error.message ||
                "Please check your card information."
            );
          } else {
            setCardError("");
          }
        }
      );

      setCardFormReady(true);
    } catch (error) {
      console.error(
        "Could not prepare card entry:",
        error
      );

      resetCardForm();

      setCardError(
        error instanceof Error
          ? error.message
          : "Could not prepare secure card entry."
      );
    } finally {
      setPreparingCard(false);
    }
  }


  function validateBookingFields() {
    if (
      !customerName.trim() ||
      !customerPhone.trim() ||
      !selectedBarberId ||
      !selectedServiceId ||
      !selectedSlot
    ) {
      setMessage(
        "Please complete all fields."
      );

      return false;
    }

    if (
      cleanPhone(customerPhone)
        .length !== 10
    ) {
      setMessage(
        "Please enter a valid 10-digit phone number."
      );

      return false;
    }

    return true;
  }


  async function submitAppointment(
    stripeSetupIntentId = null
  ) {
    const response = await fetch(
      `${API_BASE}/api/appointments`,
      {
        method: "POST",

        headers: {
          "Content-Type":
            "application/json",
        },

        body: JSON.stringify({
          shop_slug: SHOP_SLUG,

          barber_id:
            selectedBarberId,

          service_id:
            selectedServiceId,

          customer_name:
            customerName.trim(),

          customer_phone:
            customerPhone.trim(),

          notes:
            notes.trim() || null,

          start_datetime:
            selectedSlot,

          stripe_setup_intent_id:
            stripeSetupIntentId,
        }),
      }
    );

    if (response.ok) {
      return true;
    }

    let detail = "";

    try {
      const errorData =
        await response.json();

      detail =
        typeof errorData.detail ===
          "string"
          ? errorData.detail
          : "";
    } catch {
      // Use the simple message below.
    }

    console.error(
      "Appointment creation failed:",
      response.status,
      detail
    );

    throw new Error(
      detail ||
        "Could not create appointment."
    );
  }


  function finishSuccessfulBooking() {
    const bookedSlot = selectedSlot;

    setMessage(
      "Appointment booked successfully."
    );

    setSelectedSlot("");
    setNotes("");

    setAvailableSlots(
      (currentSlots) =>
        currentSlots.filter(
          (slot) =>
            slot !== bookedSlot
        )
    );

    resetCardForm();
  }


  async function reserveWithSavedCard() {
    if (
      !savedCard ||
      !verificationToken
    ) {
      return false;
    }

    setBooking(true);
    setMessage("");
    setCardError("");

    try {
      const response = await fetch(
        `${API_BASE}/api/billing/booking/setup-intent`,
        {
          method: "POST",

          headers: {
            "Content-Type":
              "application/json",
          },

          body: JSON.stringify({
            shop_slug: SHOP_SLUG,

            customer_name:
              customerName.trim(),

            customer_phone:
              customerPhone.trim(),

            use_saved_card: true,

            verification_token:
              verificationToken,
          }),
        }
      );

      const data = await response
        .json()
        .catch(() => ({}));

      if (!response.ok) {
        if (response.status === 401) {
          resetVerification();

          throw new Error(
            typeof data.detail ===
              "string"
              ? data.detail
              : "Please verify your phone again."
          );
        }

        if (response.status === 409) {
          setUseSavedCard(false);

          throw new Error(
            typeof data.detail ===
              "string"
              ? data.detail
              : "Please enter your card again."
          );
        }

        throw new Error(
          typeof data.detail ===
            "string"
            ? data.detail
            : "The saved card could not be used."
        );
      }

      if (
        !data.used_saved_card ||
        !data.setup_intent_id
      ) {
        throw new Error(
          "The saved card could not be verified."
        );
      }

      await submitAppointment(
        data.setup_intent_id
      );

      finishSuccessfulBooking();

      return true;
    } catch (error) {
      console.error(
        "Could not reserve with saved card:",
        error
      );

      setMessage(
        error instanceof Error
          ? error.message
          : "The saved card could not be used."
      );

      return false;
    } finally {
      setBooking(false);
    }
  }

  async function confirmCardAndBook() {
    if (booking) {
      return;
    }

    if (
      !stripeRef.current ||
      !cardElementRef.current ||
      !setupIntentClientSecretRef.current
    ) {
      setCardError(
        "Secure card entry is not ready. Please try again."
      );

      return;
    }

    if (!cardElementReady) {
      setCardError(
        "Secure card entry is still loading. Please try again."
      );

      return;
    }

    if (!cardComplete) {
      setCardError(
        "Please enter your complete card information."
      );

      return;
    }

    setBooking(true);
    setMessage("");
    setCardError("");

    try {
      const {
        error,
        setupIntent,
      } =
        await stripeRef.current.confirmCardSetup(
          setupIntentClientSecretRef.current,
          {
            payment_method: {
              card:
                cardElementRef.current,

              billing_details: {
                name:
                  customerName.trim(),

                phone:
                  customerPhone.trim(),
              },
            },
          }
        );

      if (error) {
        throw new Error(
          error.message ||
            "Your card could not be verified."
        );
      }

      if (
        !setupIntent ||
        setupIntent.status !==
          "succeeded"
      ) {
        throw new Error(
          "Your card could not be verified."
        );
      }

      await submitAppointment(
        setupIntent.id
      );

      finishSuccessfulBooking();
    } catch (error) {
      console.error(
        "Could not verify card and book appointment:",
        error
      );

      setCardError(
        error instanceof Error
          ? error.message
          : "Could not verify your card."
      );
    } finally {
      setBooking(false);
    }
  }


  async function createAppointment() {
    if (!validateBookingFields()) {
      return;
    }

    if (
      paymentPolicy ===
      "card_required"
    ) {
      if (
        savedCard &&
        useSavedCard
      ) {
        if (!verificationToken) {
          setMessage(
            "Please verify your phone before using your saved card."
          );

          return;
        }

        await reserveWithSavedCard();
        return;
      }

      if (!cardFormReady) {
        await prepareCardForm();
        return;
      }

      await confirmCardAndBook();
      return;
    }

    if (booking) {
      return;
    }

    setBooking(true);
    setMessage("");

    try {
      await submitAppointment();

      finishSuccessfulBooking();
    } catch (error) {
      console.error(
        "Could not create appointment:",
        error
      );

      setMessage(
        error instanceof Error
          ? error.message
          : "Could not create appointment."
      );
    } finally {
      setBooking(false);
    }
  }


  async function useDifferentCard() {
    setUseSavedCard(false);
    setMessage("");
    setCardError("");

    await prepareCardForm();
  }


  function switchBackToSavedCard() {
    resetCardForm();

    setUseSavedCard(true);
    setMessage("");
    setCardError("");
  }


  const cardRequired =
    paymentPolicy ===
    "card_required";

  const phoneReady =
    cleanPhone(customerPhone)
      .length === 10;

  const savedCardLabel =
    savedCard
      ? `${cardBrandLabel(
          savedCard.brand
        )} •••• ${savedCard.last4}`
      : "";


  return (
    <main className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-sky-50 p-4 sm:p-10">
      <div className="max-w-2xl mx-auto space-y-6">

        <section className="bg-white rounded-3xl shadow-lg p-6 border border-indigo-100">
          {shopName ? (
            <p className="text-sm font-extrabold tracking-wider text-indigo-600 mb-2">
              {shopName}
            </p>
          ) : null}

          <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-slate-900">
            Book an Appointment
          </h1>

          <p className="mt-2 text-gray-700">
            Choose your service, staff
            member, date, and time.
          </p>

          {message && (
            <p
              className={`mt-4 font-bold ${
                message ===
                "Appointment booked successfully."
                  ? "text-green-700"
                  : "text-red-700"
              }`}
            >
              {message}
            </p>
          )}
        </section>


        <section className="bg-white rounded-3xl shadow-lg p-6 border border-gray-200 space-y-5">

          <div>
            <label className="block font-bold mb-2">
              Phone Number
            </label>

            <input
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              className="w-full border rounded-2xl p-5 text-xl"
              value={customerPhone}
              onChange={
                handlePhoneChange
              }
              placeholder="240-555-1234"
            />

            {verificationStatus ===
              "idle" &&
              phoneReady && (
                <button
                  type="button"
                  onClick={
                    requestVerification
                  }
                  className="mt-3 rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-3 font-bold text-indigo-800"
                >
                  Check for saved details
                </button>
              )}

            {verificationStatus ===
              "requesting" && (
                <p className="mt-3 text-sm font-bold text-gray-600">
                  Checking your number...
                </p>
              )}

            {verificationStatus ===
              "new_customer" && (
                <p className="mt-3 text-sm font-bold text-green-700">
                  Continue below to book your
                  appointment.
                </p>
              )}

            {(verificationStatus ===
              "code_sent" ||
              verificationStatus ===
                "verifying") && (
                <div className="mt-4 rounded-2xl border border-indigo-200 bg-indigo-50 p-4">
                  <p className="font-extrabold text-slate-900">
                    Verify your phone
                  </p>

                  <p className="mt-1 text-sm text-slate-700">
                    We texted you a
                    6-digit code.
                  </p>

                  <div className="mt-3 flex flex-col sm:flex-row gap-3">
                    <input
                      inputMode="numeric"
                      autoComplete="one-time-code"
                      maxLength={6}
                      value={
                        verificationCode
                      }
                      onChange={(event) =>
                        setVerificationCode(
                          event.target.value
                            .replace(
                              /\D/g,
                              ""
                            )
                            .slice(0, 6)
                        )
                      }
                      placeholder="6-digit code"
                      className="flex-1 border rounded-xl p-4 text-xl tracking-widest bg-white"
                    />

                    <button
                      type="button"
                      onClick={
                        confirmVerification
                      }
                      disabled={
                        verificationStatus ===
                          "verifying" ||
                        verificationCode
                          .length !== 6
                      }
                      className="rounded-xl bg-indigo-600 text-white px-5 py-4 font-bold disabled:opacity-50"
                    >
                      {verificationStatus ===
                      "verifying"
                        ? "Verifying..."
                        : "Verify"}
                    </button>
                  </div>

                  <button
                    type="button"
                    onClick={
                      requestVerification
                    }
                    disabled={
                      verificationStatus ===
                      "verifying"
                    }
                    className="mt-3 text-sm font-bold text-indigo-700"
                  >
                    Send a new code
                  </button>
                </div>
              )}

            {verificationStatus ===
              "verified" &&
              verifiedCustomer && (
                <div className="mt-4 rounded-2xl border border-green-200 bg-green-50 p-4">
                  <p className="font-extrabold text-green-800">
                    ✓ Verified
                  </p>

                  <p className="mt-1 text-green-800">
                    Welcome back
                    {verifiedCustomer.name
                      ? `, ${verifiedCustomer.name}`
                      : ""}
                    .
                  </p>

                  {verifiedCustomer.last_barber_name &&
                    verifiedCustomer.last_service_name && (
                      <p className="mt-1 text-sm text-green-800">
                        We selected{" "}
                        {
                          verifiedCustomer.last_barber_name
                        }{" "}
                        and{" "}
                        {
                          verifiedCustomer.last_service_name
                        }{" "}
                        from your last
                        visit.
                      </p>
                    )}
                </div>
              )}

            {verificationMessage && (
              <p className="mt-3 font-bold text-red-700">
                {verificationMessage}
              </p>
            )}
          </div>


          <div>
            <label className="block font-bold mb-2">
              Name
            </label>

            <input
              className="w-full border rounded-2xl p-5 text-xl"
              value={customerName}
              onChange={(event) =>
                setCustomerName(
                  event.target.value
                )
              }
              placeholder="Your name"
              autoComplete="name"
            />
          </div>


          <div>
            <label className="block font-bold mb-2">
              Staff Member
            </label>

            <select
              className="w-full border rounded-2xl p-5 text-xl"
              value={
                selectedBarberId
              }
              onChange={(event) => {
                setSelectedBarberId(
                  event.target.value
                );

                setSelectedServiceId(
                  ""
                );

                setSelectedSlot("");

                setAvailableSlots(
                  []
                );
              }}
            >
              <option value="">
                Select staff member
              </option>

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


          <div>
            <label className="block font-bold mb-2">
              Service
            </label>

            <select
              className="w-full border rounded-2xl p-5 text-xl"
              value={
                selectedServiceId
              }
              disabled={
                !selectedBarberId
              }
              onChange={(event) => {
                setSelectedServiceId(
                  event.target.value
                );

                setSelectedSlot("");
              }}
            >
              <option value="">
                {selectedBarberId
                  ? "Select service"
                  : "Select staff member first"}
              </option>

              {availableServices.map(
                (service) => (
                  <option
                    key={service.id}
                    value={service.id}
                  >
                    {service.name}
                    {service.price !==
                      undefined &&
                    service.price !==
                      null
                      ? ` — $${Number(
                          service.price
                        ).toFixed(2)}`
                      : ""}
                  </option>
                )
              )}
            </select>

            {selectedService && (
              <p className="mt-2 text-sm text-gray-600">
                {selectedService.duration_minutes
                  ? `${selectedService.duration_minutes} minutes`
                  : ""}

                {selectedService.duration_minutes &&
                selectedService.price !==
                  undefined &&
                selectedService.price !==
                  null
                  ? " • "
                  : ""}

                {selectedService.price !==
                  undefined &&
                selectedService.price !==
                  null
                  ? `$${Number(
                      selectedService.price
                    ).toFixed(2)}`
                  : ""}
              </p>
            )}
          </div>


          <div>
            <label className="block font-bold mb-2">
              Date
            </label>

            <input
              type="date"
              min={today}
              className="w-full border rounded-2xl p-5 text-xl"
              value={selectedDate}
              onChange={(event) => {
                setSelectedDate(
                  event.target.value
                );

                setSelectedSlot("");
              }}
            />
          </div>


          <div>
            <label className="block font-bold mb-2">
              Available Times
            </label>

            <div className="grid grid-cols-2 gap-3">
              {availableSlots.map(
                (slot) => (
                  <button
                    key={slot}
                    type="button"
                    onClick={() =>
                      setSelectedSlot(
                        slot
                      )
                    }
                    className={`rounded-2xl p-4 font-bold border ${
                      selectedSlot ===
                      slot
                        ? "bg-black text-white"
                        : "bg-white"
                    }`}
                  >
                    {formatTime(slot)}
                  </button>
                )
              )}
            </div>

            {availableSlots.length ===
              0 && (
              <p className="mt-3 text-gray-900">
                Choose a staff member,
                service, and date to see
                times.
              </p>
            )}
          </div>


          <div>
            <label className="block font-bold mb-2">
              Notes
            </label>

            <textarea
              className="w-full border rounded-2xl p-5 min-h-28"
              value={notes}
              onChange={(event) =>
                setNotes(
                  event.target.value
                )
              }
              placeholder="Optional notes"
            />
          </div>


          {cardRequired && (
            <div className="rounded-2xl border border-violet-200 bg-violet-50 p-5">
              <div className="flex gap-3">
                <div className="text-2xl">
                  🛡️
                </div>

                <div>
                  <p className="font-extrabold text-slate-900">
                    Card required to
                    reserve
                  </p>

                  <p className="mt-1 text-sm text-slate-700">
                    This business asks
                    for a card to help
                    protect against
                    no-shows. Your card
                    is not charged just
                    for making this
                    reservation.
                  </p>
                </div>
              </div>


              {savedCard &&
                verificationStatus ===
                  "verified" &&
                useSavedCard && (
                  <div className="mt-5 rounded-2xl border border-green-200 bg-white p-4">
                    <p className="text-sm font-bold text-gray-600">
                      Card on file
                    </p>

                    <p className="mt-1 text-xl font-extrabold text-slate-900">
                      {savedCardLabel}
                    </p>

                    <p className="mt-1 text-sm text-gray-600">
                      Your saved card will
                      be used to secure
                      this reservation.
                    </p>

                    <button
                      type="button"
                      onClick={
                        useDifferentCard
                      }
                      disabled={
                        booking ||
                        preparingCard
                      }
                      className="mt-3 text-sm font-bold text-indigo-700"
                    >
                      Use a different card
                    </button>
                  </div>
                )}


              {savedCard &&
                verificationStatus ===
                  "verified" &&
                !useSavedCard && (
                  <button
                    type="button"
                    onClick={
                      switchBackToSavedCard
                    }
                    disabled={
                      booking ||
                      preparingCard
                    }
                    className="mt-4 text-sm font-bold text-indigo-700"
                  >
                    Use {savedCardLabel}
                    {" "}instead
                  </button>
                )}


              {cardFormReady &&
                !useSavedCard && (
                  <div className="mt-5 rounded-xl bg-white border border-violet-200 p-4">
                    <p className="font-bold mb-3 text-slate-900">
                      Card information
                    </p>

                    <div
                      ref={
                        cardElementContainerRef
                      }
                      className="min-h-10 py-2"
                    />

                    {!cardElementReady && (
                      <p className="mt-3 text-sm text-gray-500">
                        Loading secure card
                        entry...
                      </p>
                    )}
                  </div>
                )}


              {cardFormReady &&
                !savedCard && (
                  <div className="mt-5 rounded-xl bg-white border border-violet-200 p-4">
                    <p className="font-bold mb-3 text-slate-900">
                      Card information
                    </p>

                    <div
                      ref={
                        cardElementContainerRef
                      }
                      className="min-h-10 py-2"
                    />

                    {!cardElementReady && (
                      <p className="mt-3 text-sm text-gray-500">
                        Loading secure card
                        entry...
                      </p>
                    )}
                  </div>
                )}


              {cardError && (
                <p className="mt-4 font-bold text-red-700">
                  {cardError}
                </p>
              )}
            </div>
          )}


          <button
            type="button"
            onClick={
              createAppointment
            }
            disabled={
              booking ||
              preparingCard
            }
            className="w-full bg-black text-white rounded-2xl p-5 text-xl font-bold disabled:opacity-50"
          >
            {booking
              ? cardRequired
                ? "Reserving..."
                : "Booking..."
              : preparingCard
                ? "Opening Secure Card Entry..."
                : cardRequired &&
                    savedCard &&
                    useSavedCard
                  ? "Reserve Appointment"
                  : cardRequired &&
                      !cardFormReady
                    ? "Continue to Card"
                    : cardRequired
                      ? "Reserve Appointment"
                      : "Book Appointment"}
          </button>


          {cardRequired && (
            <p className="text-center text-xs text-gray-500">
              Card information is
              handled securely by
              Stripe.
            </p>
          )}
        </section>
      </div>
    </main>
  );
}
