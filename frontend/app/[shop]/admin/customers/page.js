"use client";

import {
  Suspense,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  useParams,
  useRouter,
  useSearchParams,
} from "next/navigation";

const API_BASE =
  "https://chairtime-production-94da.up.railway.app";

const QUICK_TAGS = [
  "VIP",
  "Loyal",
  "No-show risk",
  "Difficult",
  "Cash",
  "Family",
];

const STATUS_LABELS = {
  confirmed: "Confirmed",
  completed: "Completed",
  no_show: "No-show",
  canceled: "Canceled",
};

const STATUS_STYLES = {
  confirmed: "bg-blue-100 border-blue-300",
  completed: "bg-green-100 border-green-300",
  no_show: "bg-yellow-100 border-yellow-300",
  canceled: "bg-red-100 border-red-300",
};

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

function CustomersPageContent() {
  const params = useParams();
  const router = useRouter();
  const shopSlug = params.shop;

  const searchParams = useSearchParams();
  const selectedPhone =
    searchParams.get("phone") || "";

  const [appointments, setAppointments] = useState([]);
  const [barbers, setBarbers] = useState([]);
  const [services, setServices] = useState([]);

  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [customerSearch, setCustomerSearch] =
    useState("");

  const [
    editingCustomerKey,
    setEditingCustomerKey,
  ] = useState("");

  const [editName, setEditName] = useState("");
  const [editPhone, setEditPhone] = useState("");

  const [
    addingTagCustomerKey,
    setAddingTagCustomerKey,
  ] = useState("");

  const [customTagText, setCustomTagText] =
    useState("");

  const [
    editingNotesCustomerKey,
    setEditingNotesCustomerKey,
  ] = useState("");

  const [
    customerNotesText,
    setCustomerNotesText,
  ] = useState("");

  const [
    movingAppointmentId,
    setMovingAppointmentId,
  ] = useState("");

  const [moveDate, setMoveDate] = useState("");
  const [moveTime, setMoveTime] = useState("");
  const [savingMove, setSavingMove] =
    useState(false);

  const [
    updatingAppointmentId,
    setUpdatingAppointmentId,
  ] = useState("");

  async function loadData() {
    const query =
      "?shop_slug=" + encodeURIComponent(shopSlug);

    const [
      appointmentsRes,
      barbersRes,
      servicesRes,
    ] = await Promise.all([
      fetch(
        API_BASE + "/api/appointments" + query
      ),
      fetch(API_BASE + "/api/barbers" + query),
      fetch(API_BASE + "/api/services" + query),
    ]);

    setAppointments(
      await appointmentsRes.json()
    );

    setBarbers(await barbersRes.json());
    setServices(await servicesRes.json());
  }

  useEffect(() => {
    if (shopSlug) {
      loadData();
    }
  }, [shopSlug]);

  function barberName(id) {
    return (
      barbers.find(
        (barber) => barber.id === id
      )?.name || "Barber"
    );
  }

  function serviceName(id) {
    return (
      services.find(
        (service) => service.id === id
      )?.name || "Service"
    );
  }

  function tagList(value) {
    if (!value) {
      return [];
    }

    return String(value)
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean);
  }

  function isUpcomingAppointment(appointment) {
    const start = new Date(
      appointment.start_datetime
    );

    return (
      start.getTime() > Date.now() &&
      appointment.status !== "completed" &&
      appointment.status !== "canceled" &&
      appointment.status !== "no_show"
    );
  }

  async function updateCustomer(oldPhone) {
    setMessage("");
    setError("");

    const response = await fetch(
      API_BASE +
        "/api/customers/update?old_phone=" +
        encodeURIComponent(oldPhone) +
        "&new_name=" +
        encodeURIComponent(editName) +
        "&new_phone=" +
        encodeURIComponent(editPhone) +
        "&shop_slug=" +
        encodeURIComponent(shopSlug),
      {
        method: "PATCH",
      }
    );

    if (response.ok) {
      setMessage("Customer updated.");
      setEditingCustomerKey("");
      await loadData();
    } else {
      setError("Could not update customer.");
    }
  }

  async function updateCustomerTags(
    customerPhone,
    tags
  ) {
    setMessage("");
    setError("");

    const response = await fetch(
      API_BASE +
        "/api/customers/tags?customer_phone=" +
        encodeURIComponent(customerPhone) +
        "&customer_tags=" +
        encodeURIComponent(tags.join(",")) +
        "&shop_slug=" +
        encodeURIComponent(shopSlug),
      {
        method: "PATCH",
      }
    );

    if (response.ok) {
      setMessage("Tags updated.");
      await loadData();
    } else {
      setError("Could not update tags.");
    }
  }

  async function updateCustomerNotes(
    customerPhone
  ) {
    setMessage("");
    setError("");

    const response = await fetch(
      API_BASE +
        "/api/customers/notes?customer_phone=" +
        encodeURIComponent(customerPhone) +
        "&customer_notes=" +
        encodeURIComponent(customerNotesText) +
        "&shop_slug=" +
        encodeURIComponent(shopSlug),
      {
        method: "PATCH",
      }
    );

    if (response.ok) {
      setMessage("Customer notes saved.");
      setEditingNotesCustomerKey("");
      setCustomerNotesText("");
      await loadData();
    } else {
      setError(
        "Could not save customer notes."
      );
    }
  }

  function addCustomTag(
    customerPhone,
    activeTags
  ) {
    const cleanTag = customTagText.trim();

    if (!cleanTag) {
      setError("Enter a tag first.");
      return;
    }

    if (activeTags.includes(cleanTag)) {
      setError("That tag already exists.");
      return;
    }

    updateCustomerTags(customerPhone, [
      ...activeTags,
      cleanTag,
    ]);

    setCustomTagText("");
    setAddingTagCustomerKey("");
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
    setMoveDate("");
    setMoveTime("");
    setSavingMove(false);
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
            "Content-Type":
              "application/json",
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
      setMoveDate("");
      setMoveTime("");
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
    status
  ) {
    if (updatingAppointmentId) {
      return;
    }

    if (status === "canceled") {
      const confirmed = window.confirm(
        "Cancel this appointment?"
      );

      if (!confirmed) {
        return;
      }
    }

    setUpdatingAppointmentId(appointmentId);
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
            "Content-Type":
              "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify({
            status,
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
          STATUS_LABELS[status] || status
        }.`
      );

      await loadData();
    } catch (statusError) {
      setError(
        statusError instanceof Error
          ? statusError.message
          : "Appointment status could not be updated."
      );
    } finally {
      setUpdatingAppointmentId("");
    }
  }

  const groupedCustomers = useMemo(() => {
    const groups = {};

    appointments.forEach((appointment) => {
      const key = appointment.customer_phone;

      if (!groups[key]) {
        groups[key] = [];
      }

      groups[key].push(appointment);
    });

    let result = Object.values(groups);

    const searchText = customerSearch
      .trim()
      .toLowerCase();

    const searchDigits =
      customerSearch.replace(/\D/g, "");

    if (searchText) {
      result = result.filter(
        (appointmentsGroup) => {
          const customer =
            appointmentsGroup[0];

          const name = String(
            customer.customer_name || ""
          ).toLowerCase();

          const phone = String(
            customer.customer_phone || ""
          );

          const phoneDigits =
            phone.replace(/\D/g, "");

          return (
            name.includes(searchText) ||
            phone
              .toLowerCase()
              .includes(searchText) ||
            (searchDigits &&
              phoneDigits.includes(
                searchDigits
              ))
          );
        }
      );
    }

    if (selectedPhone) {
      result = result.sort((a, b) => {
        if (
          a[0].customer_phone ===
          selectedPhone
        ) {
          return -1;
        }

        if (
          b[0].customer_phone ===
          selectedPhone
        ) {
          return 1;
        }

        return 0;
      });
    }

    return result;
  }, [
    appointments,
    selectedPhone,
    customerSearch,
  ]);

  function appointmentCard(
    appointment,
    allowActions
  ) {
    const isMoving =
      movingAppointmentId === appointment.id;

    const status =
      appointment.status || "confirmed";

    const statusLabel =
      STATUS_LABELS[status] || "Confirmed";

    const statusStyle =
      STATUS_STYLES[status] ||
      STATUS_STYLES.confirmed;

    const busy =
      updatingAppointmentId ===
      appointment.id;

    return (
      <div
        key={appointment.id}
        className={`border rounded-2xl p-4 ${statusStyle}`}
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:justify-between sm:items-start">
          <div>
            <p className="font-bold">
              {new Date(
                appointment.start_datetime
              ).toLocaleString()}
            </p>

            <p>
              {serviceName(
                appointment.service_id
              )}{" "}
              ·{" "}
              {barberName(
                appointment.barber_id
              )}
            </p>

            {appointment.notes && (
              <p className="mt-1">
                {appointment.notes}
              </p>
            )}
          </div>

          <span className="bg-white border rounded-full px-3 py-1 text-sm font-bold self-start">
            {statusLabel}
          </span>
        </div>

        {allowActions && !isMoving && (
          <div className="flex flex-wrap gap-2 mt-4">
            <button
              type="button"
              onClick={() =>
                startMove(appointment)
              }
              disabled={busy}
              className="bg-purple-600 text-white px-3 py-2 rounded-xl font-semibold disabled:opacity-60"
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
              disabled={busy}
              className="bg-blue-500 text-white px-3 py-2 rounded-xl font-semibold disabled:opacity-60"
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
              disabled={busy}
              className="bg-green-600 text-white px-3 py-2 rounded-xl font-semibold disabled:opacity-60"
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
              disabled={busy}
              className="bg-yellow-500 text-white px-3 py-2 rounded-xl font-semibold disabled:opacity-60"
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
              disabled={busy}
              className="bg-red-500 text-white px-3 py-2 rounded-xl font-semibold disabled:opacity-60"
            >
              {busy
                ? "Updating..."
                : "Cancel"}
            </button>
          </div>
        )}

        {allowActions && isMoving && (
          <div className="mt-4 bg-white border rounded-xl p-4">
            <p className="font-bold mb-3">
              Move this appointment
            </p>

            <div className="grid gap-3 sm:grid-cols-3">
              <input
                type="date"
                value={moveDate}
                onChange={(event) =>
                  setMoveDate(
                    event.target.value
                  )
                }
                className="border rounded-xl p-3"
              />

              <input
                type="time"
                value={moveTime}
                onChange={(event) =>
                  setMoveTime(
                    event.target.value
                  )
                }
                className="border rounded-xl p-3"
              />

              <button
                type="button"
                onClick={() =>
                  saveMove(appointment.id)
                }
                disabled={savingMove}
                className="bg-black text-white rounded-xl p-3 font-bold disabled:opacity-60"
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
              className="mt-3 bg-gray-300 px-4 py-2 rounded-xl font-semibold disabled:opacity-60"
            >
              Cancel Move
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-purple-50 p-4 sm:p-8">
      <div className="max-w-5xl mx-auto space-y-6">
        <section className="rounded-3xl shadow-lg p-6 border border-purple-200 bg-gradient-to-r from-purple-100 via-fuchsia-50 to-white">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-sm font-extrabold uppercase tracking-widest text-purple-700 mb-2">
                {displayShopName(shopSlug)}
              </p>

              <h1 className="text-5xl font-extrabold tracking-tight text-gray-950">
                Customers
              </h1>

              <p className="mt-2 text-lg text-gray-700">
                Find customers, review history, and manage upcoming appointments.
              </p>
            </div>

            <button
              type="button"
              onClick={() =>
                router.push(
                  `/${shopSlug}/admin`
                )
              }
              className="inline-flex items-center justify-center rounded-xl bg-blue-600 px-5 py-3 font-bold text-white shadow hover:bg-blue-700"
            >
              Admin Home
            </button>
          </div>
        </section>

        <section className="bg-white rounded-3xl p-5 shadow-lg border border-purple-200">
          <label className="block text-lg font-bold mb-2 text-purple-950">
            Search customers
          </label>

          <input
            type="search"
            value={customerSearch}
            onChange={(event) =>
              setCustomerSearch(
                event.target.value
              )
            }
            placeholder="Search by name or phone"
            className="w-full border border-purple-200 rounded-xl p-4 text-lg bg-purple-50 focus:outline-none focus:ring-2 focus:ring-purple-300"
          />

          {customerSearch &&
            groupedCustomers.length === 0 && (
              <p className="mt-3 text-gray-600">
                No customers found.
              </p>
            )}
        </section>

        {message && (
          <p className="rounded-xl bg-green-50 border border-green-200 px-4 py-3 font-bold text-green-700">
            {message}
          </p>
        )}

        {error && (
          <p className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 font-bold text-red-700">
            {error}
          </p>
        )}

        {groupedCustomers.map(
          (appointmentsGroup) => {
            const latest =
              appointmentsGroup[0];

            const customerKey =
              latest.customer_phone;

            const activeTags = tagList(
              latest.customer_tags
            );

            const isHighlighted =
              selectedPhone === customerKey;

            const isAddingTag =
              addingTagCustomerKey ===
              customerKey;

            const isEditingNotes =
              editingNotesCustomerKey ===
              customerKey;

            const upcomingAppointments =
              appointmentsGroup
                .filter(
                  isUpcomingAppointment
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

            const pastAppointments =
              appointmentsGroup
                .filter(
                  (appointment) =>
                    !isUpcomingAppointment(
                      appointment
                    )
                )
                .sort(
                  (a, b) =>
                    new Date(
                      b.start_datetime
                    ) -
                    new Date(
                      a.start_datetime
                    )
                );

            return (
              <section
                key={customerKey}
                className={
                  isHighlighted
                    ? "bg-white rounded-3xl p-6 shadow-xl border-4 border-purple-500"
                    : "bg-white rounded-3xl p-6 shadow-lg border border-purple-200"
                }
              >
                <div className="flex flex-col gap-4 sm:flex-row sm:justify-between sm:items-center">
                  <div>
                    <h2 className="text-3xl font-extrabold text-purple-950">
                      {latest.customer_name}
                    </h2>

                    <p className="text-lg text-gray-700">
                      {latest.customer_phone}
                    </p>

                    <div className="flex gap-2 mt-2 flex-wrap">
                      {activeTags.map(
                        (tag) => (
                          <span
                            key={tag}
                            className="px-3 py-1 rounded-full bg-purple-100 text-purple-900 font-semibold"
                          >
                            {tag}
                          </span>
                        )
                      )}
                    </div>
                  </div>

                  <div className="flex gap-2 flex-wrap">
                    <a
                      href={
                        "tel:" +
                        latest.customer_phone
                      }
                      className="bg-black text-white px-4 py-2 rounded-xl font-semibold"
                    >
                      Call
                    </a>

                    <a
                      href={
                        "sms:" +
                        latest.customer_phone
                      }
                      className="bg-blue-700 text-white px-4 py-2 rounded-xl font-semibold"
                    >
                      Text
                    </a>

                    <button
                      type="button"
                      onClick={() => {
                        setEditingCustomerKey(
                          customerKey
                        );

                        setEditName(
                          latest.customer_name
                        );

                        setEditPhone(
                          latest.customer_phone
                        );
                      }}
                      className="bg-green-600 text-white px-4 py-2 rounded-xl font-semibold"
                    >
                      Edit
                    </button>
                  </div>
                </div>

                <div className="mt-5 flex gap-2 flex-wrap">
                  {QUICK_TAGS.map((tag) => {
                    const active =
                      activeTags.includes(tag);

                    return (
                      <button
                        type="button"
                        key={tag}
                        onClick={() => {
                          const nextTags =
                            active
                              ? activeTags.filter(
                                  (
                                    activeTag
                                  ) =>
                                    activeTag !==
                                    tag
                                )
                              : [
                                  ...activeTags,
                                  tag,
                                ];

                          updateCustomerTags(
                            latest.customer_phone,
                            nextTags
                          );
                        }}
                        className={
                          active
                            ? "bg-purple-700 text-white px-3 py-2 rounded-full font-semibold"
                            : "bg-purple-100 text-purple-950 px-3 py-2 rounded-full font-semibold"
                        }
                      >
                        {tag}
                      </button>
                    );
                  })}

                  <button
                    type="button"
                    onClick={() => {
                      setAddingTagCustomerKey(
                        customerKey
                      );

                      setCustomTagText("");
                    }}
                    className="bg-purple-950 text-white px-3 py-2 rounded-full font-semibold"
                  >
                    + Add Tag
                  </button>
                </div>

                {isAddingTag && (
                  <div className="mt-4 bg-purple-50 border border-purple-200 p-4 rounded-2xl">
                    <input
                      className="border border-purple-200 p-3 rounded-xl w-full mb-2 bg-white"
                      placeholder="Type custom tag"
                      value={customTagText}
                      onChange={(event) =>
                        setCustomTagText(
                          event.target.value
                        )
                      }
                    />

                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() =>
                          addCustomTag(
                            latest.customer_phone,
                            activeTags
                          )
                        }
                        className="bg-purple-700 text-white px-4 py-2 rounded-xl font-semibold"
                      >
                        Save Tag
                      </button>

                      <button
                        type="button"
                        onClick={() => {
                          setAddingTagCustomerKey(
                            ""
                          );

                          setCustomTagText("");
                        }}
                        className="bg-gray-300 px-4 py-2 rounded-xl font-semibold"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}

                <div className="mt-5 bg-amber-50 border border-amber-200 p-4 rounded-2xl">
                  <div className="flex justify-between items-center gap-3 mb-2">
                    <p className="font-bold text-lg">
                      Customer Notes
                    </p>

                    <button
                      type="button"
                      onClick={() => {
                        setEditingNotesCustomerKey(
                          customerKey
                        );

                        setCustomerNotesText(
                          latest.customer_notes ||
                            ""
                        );
                      }}
                      className="bg-amber-600 text-white px-3 py-2 rounded-xl font-semibold"
                    >
                      Edit Notes
                    </button>
                  </div>

                  {latest.customer_notes ? (
                    <p className="whitespace-pre-wrap">
                      {
                        latest.customer_notes
                      }
                    </p>
                  ) : (
                    <p className="text-gray-600">
                      No permanent customer notes.
                    </p>
                  )}
                </div>

                {isEditingNotes && (
                  <div className="mt-4 bg-amber-50 border border-amber-200 p-4 rounded-2xl">
                    <textarea
                      className="border border-amber-200 p-3 rounded-xl w-full mb-2 min-h-32 bg-white"
                      placeholder="Permanent customer notes"
                      value={customerNotesText}
                      onChange={(event) =>
                        setCustomerNotesText(
                          event.target.value
                        )
                      }
                    />

                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() =>
                          updateCustomerNotes(
                            latest.customer_phone
                          )
                        }
                        className="bg-black text-white px-4 py-2 rounded-xl font-semibold"
                      >
                        Save Notes
                      </button>

                      <button
                        type="button"
                        onClick={() => {
                          setEditingNotesCustomerKey(
                            ""
                          );

                          setCustomerNotesText(
                            ""
                          );
                        }}
                        className="bg-gray-300 px-4 py-2 rounded-xl font-semibold"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}

                {editingCustomerKey ===
                  customerKey && (
                  <div className="mt-4 bg-green-50 border border-green-200 p-4 rounded-2xl">
                    <label className="block font-bold mb-2">
                      Customer name
                    </label>

                    <input
                      className="border p-3 rounded-xl w-full mb-3 bg-white"
                      value={editName}
                      onChange={(event) =>
                        setEditName(
                          event.target.value
                        )
                      }
                    />

                    <label className="block font-bold mb-2">
                      Phone
                    </label>

                    <input
                      className="border p-3 rounded-xl w-full mb-3 bg-white"
                      value={editPhone}
                      onChange={(event) =>
                        setEditPhone(
                          event.target.value
                        )
                      }
                    />

                    <button
                      type="button"
                      onClick={() =>
                        updateCustomer(
                          latest.customer_phone
                        )
                      }
                      className="bg-green-700 text-white px-4 py-2 rounded-xl font-semibold"
                    >
                      Save Customer
                    </button>
                  </div>
                )}

                <div className="mt-7">
                  <h3 className="text-2xl font-extrabold text-purple-950 mb-3">
                    Upcoming Appointments
                  </h3>

                  {upcomingAppointments.length >
                  0 ? (
                    <div className="space-y-3">
                      {upcomingAppointments.map(
                        (appointment) =>
                          appointmentCard(
                            appointment,
                            true
                          )
                      )}
                    </div>
                  ) : (
                    <div className="border border-purple-100 rounded-2xl p-4 bg-purple-50">
                      <p className="text-gray-600">
                        No upcoming appointments.
                      </p>
                    </div>
                  )}
                </div>

                <div className="mt-7">
                  <h3 className="text-2xl font-extrabold text-purple-950 mb-3">
                    Past Appointments
                  </h3>

                  {pastAppointments.length >
                  0 ? (
                    <div className="space-y-3">
                      {pastAppointments.map(
                        (appointment) =>
                          appointmentCard(
                            appointment,
                            false
                          )
                      )}
                    </div>
                  ) : (
                    <div className="border border-purple-100 rounded-2xl p-4 bg-purple-50">
                      <p className="text-gray-600">
                        No past appointments.
                      </p>
                    </div>
                  )}
                </div>
              </section>
            );
          }
        )}
      </div>
    </main>
  );
}

export default function CustomersPage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen bg-purple-50 p-6">
          <div className="max-w-5xl mx-auto bg-white rounded-3xl p-6 shadow">
            <p className="text-xl font-bold">
              Loading customers...
            </p>
          </div>
        </main>
      }
    >
      <CustomersPageContent />
    </Suspense>
  );
}
