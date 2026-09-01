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
    appointments,
    setAppointments,
  ] = useState([]);

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
        appointmentsRes,
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

        fetch(
          `${API_BASE}/api/appointments${query}`
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

      if (appointmentsRes.ok) {
        setAppointments(
          await appointmentsRes.json()
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


  function cleanPhone(phone) {
    return String(phone || "").replace(
      /\D/g,
      ""
    );
  }


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


  const recognizedCustomer =
    useMemo(() => {
      const phone =
        cleanPhone(customerPhone);

      if (!phone || !SHOP_SLUG) {
        return null;
      }

      return (
        appointments
          .filter(
            (appointment) =>
              appointment.shop_slug ===
                SHOP_SLUG &&
              cleanPhone(
                appointment.customer_phone
              ) === phone
          )
          .sort(
            (a, b) =>
              new Date(
                b.start_datetime
              ) -
              new Date(
                a.start_datetime
              )
          )[0] || null
      );
    }, [
      appointments,
      customerPhone,
      SHOP_SLUG,
    ]);


  useEffect(() => {
    if (!recognizedCustomer) {
      return;
    }

    if (!customerName) {
      setCustomerName(
        recognizedCustomer.customer_name
      );
    }

    if (
      recognizedCustomer.barber_id
    ) {
      setSelectedBarberId(
        recognizedCustomer.barber_id
      );
    }

    if (
      recognizedCustomer.service_id
    ) {
      setSelectedServiceId(
        recognizedCustomer.service_id
      );
    }
  }, [
    recognizedCustomer,
    customerName,
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


  function barberName(id) {
    return (
      barbers.find(
        (barber) =>
          barber.id === id
      )?.name || "staff member"
    );
  }


  function serviceName(id) {
    return (
      services.find(
        (service) =>
          service.id === id
      )?.name || "service"
    );
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

    return true;
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


  async function createAppointment() {
    if (!validateBookingFields()) {
      return;
    }

    if (
      paymentPolicy ===
      "card_required"
    ) {
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

      setMessage(
        "Appointment booked successfully."
      );

      setSelectedSlot("");
      setNotes("");

      await loadData();
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

      setMessage(
        "Appointment booked successfully."
      );

      setSelectedSlot("");
      setNotes("");

      resetCardForm();

      await loadData();
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


  const cardRequired =
    paymentPolicy ===

    
    "card_required";

  return (
    <main className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-sky-50 p-4 sm:p-10">
      <div className="max-w-2xl mx-auto space-y-6">
        <section className="bg-white rounded-3xl shadow-lg p-6 border border-indigo-100">
          {shopName ? (
            <p className="text-sm font-extrabold tracking-wider text-indigo-600 uppercase mb-2">
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
              className="w-full border rounded-2xl p-5 text-xl"
              value={customerPhone}
              onChange={(event) =>
                setCustomerPhone(
                  event.target.value
                )
              }
              placeholder="240-555-1234"
            />

            {recognizedCustomer && (
              <p className="mt-2 text-green-700 font-bold">
                Welcome back,{" "}
                {
                  recognizedCustomer.customer_name
                }
                . We selected{" "}
                {barberName(
                  recognizedCustomer.barber_id
                )}{" "}
                and{" "}
                {serviceName(
                  recognizedCustomer.service_id
                )}{" "}
                from your last visit.
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

              {cardFormReady && (
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
