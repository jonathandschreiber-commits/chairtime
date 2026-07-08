"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";

const API_BASE = "https://chairtime-production-94da.up.railway.app";

const QUICK_TAGS = [
  "VIP",
  "Loyal",
  "No-show risk",
  "Difficult",
  "Cash",
  "Family",
];

function CustomersPageContent() {
  const params = useParams();
  const shopSlug = params.shop;

  const searchParams = useSearchParams();
  const selectedPhone = searchParams.get("phone") || "";

  const [appointments, setAppointments] = useState([]);
  const [barbers, setBarbers] = useState([]);
  const [services, setServices] = useState([]);
  const [message, setMessage] = useState("");

  const [editingCustomerKey, setEditingCustomerKey] = useState("");
  const [editName, setEditName] = useState("");
  const [editPhone, setEditPhone] = useState("");

  const [addingTagCustomerKey, setAddingTagCustomerKey] = useState("");
  const [customTagText, setCustomTagText] = useState("");

  const [editingNotesCustomerKey, setEditingNotesCustomerKey] = useState("");
  const [customerNotesText, setCustomerNotesText] = useState("");

  async function loadData() {
    const query = "?shop_slug=" + encodeURIComponent(shopSlug);

    const [appointmentsRes, barbersRes, servicesRes] = await Promise.all([
      fetch(API_BASE + "/api/appointments" + query),
      fetch(API_BASE + "/api/barbers" + query),
      fetch(API_BASE + "/api/services" + query),
    ]);

    setAppointments(await appointmentsRes.json());
    setBarbers(await barbersRes.json());
    setServices(await servicesRes.json());
  }

  useEffect(() => {
    if (shopSlug) {
      loadData();
    }
  }, [shopSlug]);

  function barberName(id) {
    return barbers.find((b) => b.id === id)?.name || "Barber";
  }

  function serviceName(id) {
    return services.find((s) => s.id === id)?.name || "Service";
  }

  function tagList(value) {
    if (!value) return [];
    return String(value)
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean);
  }

  async function updateCustomer(oldPhone) {
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
      { method: "PATCH" }
    );

    if (response.ok) {
      setMessage("Customer updated.");
      setEditingCustomerKey("");
      loadData();
    } else {
      setMessage("Could not update customer.");
    }
  }

  async function updateCustomerTags(customerPhone, tags) {
    const response = await fetch(
      API_BASE +
        "/api/customers/tags?customer_phone=" +
        encodeURIComponent(customerPhone) +
        "&customer_tags=" +
        encodeURIComponent(tags.join(",")) +
        "&shop_slug=" +
        encodeURIComponent(shopSlug),
      { method: "PATCH" }
    );

    if (response.ok) {
      setMessage("Tags updated.");
      loadData();
    } else {
      setMessage("Could not update tags.");
    }
  }

  async function updateCustomerNotes(customerPhone) {
    const response = await fetch(
      API_BASE +
        "/api/customers/notes?customer_phone=" +
        encodeURIComponent(customerPhone) +
        "&customer_notes=" +
        encodeURIComponent(customerNotesText) +
        "&shop_slug=" +
        encodeURIComponent(shopSlug),
      { method: "PATCH" }
    );

    if (response.ok) {
      setMessage("Customer notes saved.");
      setEditingNotesCustomerKey("");
      setCustomerNotesText("");
      loadData();
    } else {
      setMessage("Could not save customer notes.");
    }
  }

  function addCustomTag(customerPhone, activeTags) {
    const cleanTag = customTagText.trim();

    if (!cleanTag) {
      setMessage("Enter a tag first.");
      return;
    }

    if (activeTags.includes(cleanTag)) {
      setMessage("That tag already exists.");
      return;
    }

    updateCustomerTags(customerPhone, [...activeTags, cleanTag]);
    setCustomTagText("");
    setAddingTagCustomerKey("");
  }

  const groupedCustomers = useMemo(() => {
    const groups = {};

    appointments.forEach((appointment) => {
      const key = appointment.customer_phone;
      if (!groups[key]) groups[key] = [];
      groups[key].push(appointment);
    });

    let result = Object.values(groups);

    if (selectedPhone) {
      result = result.sort((a, b) => {
        if (a[0].customer_phone === selectedPhone) return -1;
        if (b[0].customer_phone === selectedPhone) return 1;
        return 0;
      });
    }

    return result;
  }, [appointments, selectedPhone]);

  return (
    <main className="min-h-screen bg-gray-100 p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        <h1 className="text-4xl font-bold">{shopSlug} Customers</h1>

        {message && <p className="font-bold text-green-700">{message}</p>}

        {groupedCustomers.map((appointmentsGroup) => {
          const latest = appointmentsGroup[0];
          const customerKey = latest.customer_phone;
          const activeTags = tagList(latest.customer_tags);
          const isHighlighted = selectedPhone === customerKey;
          const isAddingTag = addingTagCustomerKey === customerKey;
          const isEditingNotes = editingNotesCustomerKey === customerKey;

          return (
            <div
              key={customerKey}
              className={
                isHighlighted
                  ? "bg-yellow-50 rounded-2xl p-6 shadow border-4 border-yellow-400"
                  : "bg-white rounded-2xl p-6 shadow border"
              }
            >
              <div className="flex justify-between items-center gap-4">
                <div>
                  <h2 className="text-2xl font-bold">
                    {latest.customer_name}
                  </h2>

                  <p>{latest.customer_phone}</p>

                  <div className="flex gap-2 mt-2 flex-wrap">
                    {activeTags.map((tag) => (
                      <span
                        key={tag}
                        className="px-3 py-1 rounded-full bg-purple-100"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="flex gap-2 flex-wrap justify-end">
                  <a
                    href={"tel:" + latest.customer_phone}
                    className="bg-black text-white px-4 py-2 rounded-xl"
                  >
                    Call
                  </a>

                  <a
                    href={"sms:" + latest.customer_phone}
                    className="bg-blue-700 text-white px-4 py-2 rounded-xl"
                  >
                    Text
                  </a>

                  <button
                    onClick={() => {
                      setEditingCustomerKey(customerKey);
                      setEditName(latest.customer_name);
                      setEditPhone(latest.customer_phone);
                    }}
                    className="bg-green-600 text-white px-4 py-2 rounded-xl"
                  >
                    Edit
                  </button>
                </div>
              </div>

              <div className="mt-4 flex gap-2 flex-wrap">
                {QUICK_TAGS.map((tag) => {
                  const active = activeTags.includes(tag);

                  return (
                    <button
                      key={tag}
                      onClick={() => {
                        const nextTags = active
                          ? activeTags.filter((t) => t !== tag)
                          : [...activeTags, tag];

                        updateCustomerTags(latest.customer_phone, nextTags);
                      }}
                      className={
                        active
                          ? "bg-purple-700 text-white px-3 py-2 rounded-full"
                          : "bg-gray-200 px-3 py-2 rounded-full"
                      }
                    >
                      {tag}
                    </button>
                  );
                })}

                <button
                  onClick={() => {
                    setAddingTagCustomerKey(customerKey);
                    setCustomTagText("");
                  }}
                  className="bg-black text-white px-3 py-2 rounded-full"
                >
                  Add Tag
                </button>
              </div>

              {isAddingTag && (
                <div className="mt-4 bg-purple-50 p-4 rounded-xl">
                  <input
                    className="border p-3 rounded w-full mb-2"
                    placeholder="Type custom tag"
                    value={customTagText}
                    onChange={(event) => setCustomTagText(event.target.value)}
                  />

                  <div className="flex gap-2">
                    <button
                      onClick={() =>
                        addCustomTag(latest.customer_phone, activeTags)
                      }
                      className="bg-black text-white px-4 py-2 rounded-xl"
                    >
                      Save Tag
                    </button>

                    <button
                      onClick={() => {
                        setAddingTagCustomerKey("");
                        setCustomTagText("");
                      }}
                      className="bg-gray-300 px-4 py-2 rounded-xl"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              <div className="mt-4 bg-yellow-50 p-4 rounded-xl">
                <div className="flex justify-between items-center mb-2">
                  <p className="font-bold">Customer Notes</p>

                  <button
                    onClick={() => {
                      setEditingNotesCustomerKey(customerKey);
                      setCustomerNotesText(latest.customer_notes || "");
                    }}
                    className="bg-yellow-600 text-white px-3 py-2 rounded-xl"
                  >
                    Edit Notes
                  </button>
                </div>

                {latest.customer_notes ? (
                  <p className="whitespace-pre-wrap">{latest.customer_notes}</p>
                ) : (
                  <p className="text-gray-600">No permanent customer notes.</p>
                )}
              </div>

              {isEditingNotes && (
                <div className="mt-4 bg-yellow-50 p-4 rounded-xl">
                  <textarea
                    className="border p-3 rounded w-full mb-2 min-h-32"
                    placeholder="Permanent customer notes"
                    value={customerNotesText}
                    onChange={(event) =>
                      setCustomerNotesText(event.target.value)
                    }
                  />

                  <div className="flex gap-2">
                    <button
                      onClick={() =>
                        updateCustomerNotes(latest.customer_phone)
                      }
                      className="bg-black text-white px-4 py-2 rounded-xl"
                    >
                      Save Notes
                    </button>

                    <button
                      onClick={() => {
                        setEditingNotesCustomerKey("");
                        setCustomerNotesText("");
                      }}
                      className="bg-gray-300 px-4 py-2 rounded-xl"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {editingCustomerKey === customerKey && (
                <div className="mt-4 bg-green-50 p-4 rounded-xl">
                  <input
                    className="border p-3 rounded w-full mb-2"
                    value={editName}
                    onChange={(event) => setEditName(event.target.value)}
                  />

                  <input
                    className="border p-3 rounded w-full mb-2"
                    value={editPhone}
                    onChange={(event) => setEditPhone(event.target.value)}
                  />

                  <button
                    onClick={() => updateCustomer(latest.customer_phone)}
                    className="bg-black text-white px-4 py-2 rounded-xl"
                  >
                    Save Customer
                  </button>
                </div>
              )}

              <div className="mt-4 space-y-2">
                {appointmentsGroup.map((appointment) => (
                  <div
                    key={appointment.id}
                    className="border rounded-xl p-3 bg-gray-50"
                  >
                    <p className="font-bold">
                      {new Date(appointment.start_datetime).toLocaleString()}
                    </p>

                    <p>
                      {serviceName(appointment.service_id)} ·{" "}
                      {barberName(appointment.barber_id)}
                    </p>

                    {appointment.notes && <p>{appointment.notes}</p>}
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </main>
  );
}

export default function CustomersPage() {
  return (
    <Suspense fallback={<main className="p-6">Loading customers...</main>}>
      <CustomersPageContent />
    </Suspense>
  );
}