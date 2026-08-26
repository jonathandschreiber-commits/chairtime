"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

const API_BASE =
  "https://chairtime-production-94da.up.railway.app";

export default function StaffServicesPage() {
  const params = useParams();
  const shopSlug = params.shop;

  const [barbers, setBarbers] = useState([]);
  const [services, setServices] = useState([]);

  const [newBarberName, setNewBarberName] =
    useState("");

  const [
    editingBarberId,
    setEditingBarberId,
  ] = useState("");

  const [
    editedBarberName,
    setEditedBarberName,
  ] = useState("");

  const [newServiceName, setNewServiceName] =
    useState("");

  const [
    editingServiceId,
    setEditingServiceId,
  ] = useState("");

  const [
    editedServiceName,
    setEditedServiceName,
  ] = useState("");

  const [staffMessage, setStaffMessage] =
    useState("");

  const [
    serviceMessage,
    setServiceMessage,
  ] = useState("");

  async function loadData() {
    if (!shopSlug) return;

    const [
      barbersResponse,
      servicesResponse,
    ] = await Promise.all([
      fetch(
        `${API_BASE}/api/barbers?shop_slug=${encodeURIComponent(
          shopSlug
        )}`
      ),

      fetch(
        `${API_BASE}/api/service-catalog?shop_slug=${encodeURIComponent(
          shopSlug
        )}`
      ),
    ]);

    if (!barbersResponse.ok) {
      setStaffMessage(
        "Could not load staff."
      );
      return;
    }

    if (!servicesResponse.ok) {
      setServiceMessage(
        "Could not load services."
      );
      return;
    }

    setBarbers(
      await barbersResponse.json()
    );

    setServices(
      await servicesResponse.json()
    );
  }

  useEffect(() => {
    loadData();
  }, [shopSlug]);

  async function addBarber() {
    const cleanName =
      newBarberName.trim();

    if (!cleanName) {
      setStaffMessage(
        "Enter a staff name."
      );
      return;
    }

    const existingBarber =
      barbers[0];

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
            existingBarber?.shop_name ||
            "ChairTime Barbershop",
          phone: "",
          timezone:
            existingBarber?.timezone ||
            "America/New_York",
          shop_slug: shopSlug,
        }),
      }
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({}));

      setStaffMessage(
        error.detail ||
          "Could not add staff member."
      );

      return;
    }

    setNewBarberName("");
    setStaffMessage(
      "Staff member added."
    );

    loadData();
  }

  function startEditingBarber(
    barber
  ) {
    setEditingBarberId(
      barber.id
    );

    setEditedBarberName(
      barber.name
    );

    setStaffMessage("");
  }

  function cancelEditingBarber() {
    setEditingBarberId("");
    setEditedBarberName("");
  }

  async function updateBarber(id) {
    const cleanName =
      editedBarberName.trim();

    if (!cleanName) {
      setStaffMessage(
        "Enter a staff name."
      );
      return;
    }

    const response = await fetch(
      `${API_BASE}/api/barbers/${encodeURIComponent(
        id
      )}`,
      {
        method: "PATCH",
        headers: {
          "Content-Type":
            "application/json",
        },
        body: JSON.stringify({
          name: cleanName,
        }),
      }
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({}));

      setStaffMessage(
        error.detail ||
          "Could not update staff member."
      );

      return;
    }

    cancelEditingBarber();

    setStaffMessage(
      "Staff member updated."
    );

    loadData();
  }

  async function deleteBarber(
    barber
  ) {
    const confirmed =
      window.confirm(
        `Delete ${barber.name}?`
      );

    if (!confirmed) return;

    const response = await fetch(
      `${API_BASE}/api/barbers/${encodeURIComponent(
        barber.id
      )}`,
      {
        method: "DELETE",
      }
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({}));

      setStaffMessage(
        error.detail ||
          "Could not delete staff member."
      );

      return;
    }

    setStaffMessage(
      "Staff member deleted."
    );

    loadData();
  }

  async function addService() {
    const cleanName =
      newServiceName.trim();

    if (!cleanName) {
      setServiceMessage(
        "Enter a service name."
      );
      return;
    }

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

      setServiceMessage(
        typeof error.detail ===
          "string"
          ? error.detail
          : "Could not add service."
      );

      return;
    }

    setNewServiceName("");

    setServiceMessage(
      "Service added."
    );

    loadData();
  }

  function startEditingService(
    service
  ) {
    setEditingServiceId(
      service.id
    );

    setEditedServiceName(
      service.name
    );

    setServiceMessage("");
  }

  function cancelEditingService() {
    setEditingServiceId("");
    setEditedServiceName("");
  }

  async function updateService(id) {
    const cleanName =
      editedServiceName.trim();

    if (!cleanName) {
      setServiceMessage(
        "Enter a service name."
      );
      return;
    }

    const response = await fetch(
      `${API_BASE}/api/service-catalog/${encodeURIComponent(
        id
      )}`,
      {
        method: "PATCH",
        headers: {
          "Content-Type":
            "application/json",
        },
        body: JSON.stringify({
          name: cleanName,
        }),
      }
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({}));

      setServiceMessage(
        typeof error.detail ===
          "string"
          ? error.detail
          : "Could not update service."
      );

      return;
    }

    cancelEditingService();

    setServiceMessage(
      "Service updated."
    );

    loadData();
  }

  async function deleteService(
    service
  ) {
    const confirmed =
      window.confirm(
        `Delete ${service.name} from the shop's service list?`
      );

    if (!confirmed) return;

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
        typeof error.detail ===
          "object"
      ) {
        const staff =
          error.detail
            .assigned_staff || [];

        if (staff.length > 0) {
          setServiceMessage(
            `${service.name} is currently assigned to: ${staff.join(
              ", "
            )}. Remove those assignments in Shop Setup first.`
          );

          return;
        }
      }

      setServiceMessage(
        typeof error.detail ===
          "string"
          ? error.detail
          : "Could not delete service."
      );

      return;
    }

    setServiceMessage(
      "Service deleted."
    );

    loadData();
  }

  return (
    <main className="min-h-screen bg-rose-50 p-4 sm:p-8">
      <div className="max-w-4xl mx-auto space-y-6">
        <section className="rounded-3xl shadow-lg p-6 border border-rose-200 bg-gradient-to-r from-rose-100 via-pink-50 to-white">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-sm font-extrabold uppercase tracking-widest text-rose-700 mb-2">
                {shopSlug}
              </p>

              <h1 className="text-5xl font-extrabold tracking-tight text-gray-950">
                Staff & Services
              </h1>

              <p className="text-lg text-gray-700 mt-2">
                Manage the shop's staff and master service list.
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

        <section className="bg-white rounded-3xl shadow-lg p-6 border border-rose-200 space-y-4">
          <div>
            <p className="text-sm font-extrabold uppercase tracking-widest text-rose-600 mb-1">
              Team
            </p>

            <h2 className="text-3xl font-extrabold text-rose-950">
              Staff
            </h2>

            <p className="text-gray-600 mt-1">
              Add or manage the people who take appointments.
            </p>
          </div>

          {staffMessage && (
            <div className="bg-green-100 border border-green-200 p-3 rounded-xl font-bold text-green-800">
              {staffMessage}
            </div>
          )}

          <div className="rounded-2xl bg-rose-50 border border-rose-100 p-4 space-y-3">
            <label className="block font-bold text-rose-950">
              Add staff member
            </label>

            <input
              type="text"
              value={newBarberName}
              onChange={(event) =>
                setNewBarberName(
                  event.target.value
                )
              }
              placeholder="Staff name"
              className="border border-rose-200 bg-white p-3 rounded-xl w-full focus:outline-none focus:ring-2 focus:ring-rose-300"
            />

            <button
              onClick={addBarber}
              className="bg-rose-700 hover:bg-rose-800 text-white px-5 py-3 rounded-xl font-bold shadow"
            >
              + Add Staff Member
            </button>
          </div>

          <div className="space-y-3">
            {barbers.length === 0 ? (
              <div className="border border-rose-100 rounded-2xl p-4 bg-rose-50">
                <p className="text-gray-600">
                  No staff members yet.
                </p>
              </div>
            ) : (
              barbers.map((barber) => (
                <div
                  key={barber.id}
                  className="border border-rose-200 rounded-2xl p-4 bg-white shadow-sm"
                >
                  {editingBarberId ===
                  barber.id ? (
                    <div className="space-y-3">
                      <input
                        type="text"
                        value={
                          editedBarberName
                        }
                        onChange={(
                          event
                        ) =>
                          setEditedBarberName(
                            event.target
                              .value
                          )
                        }
                        className="border border-rose-200 p-3 rounded-xl w-full focus:outline-none focus:ring-2 focus:ring-rose-300"
                      />

                      <div className="flex gap-2">
                        <button
                          onClick={() =>
                            updateBarber(
                              barber.id
                            )
                          }
                          className="bg-rose-700 text-white px-4 py-2 rounded-xl font-semibold"
                        >
                          Save
                        </button>

                        <button
                          onClick={
                            cancelEditingBarber
                          }
                          className="bg-gray-200 px-4 py-2 rounded-xl font-semibold"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-3 sm:flex-row sm:justify-between sm:items-center">
                      <div>
                        <p className="text-xl font-extrabold text-rose-950">
                          {barber.name}
                        </p>

                        <p className="text-sm text-gray-500">
                          Staff member
                        </p>
                      </div>

                      <div className="flex gap-2">
                        <button
                          onClick={() =>
                            startEditingBarber(
                              barber
                            )
                          }
                          className="bg-rose-700 text-white px-4 py-2 rounded-xl font-semibold"
                        >
                          Edit
                        </button>

                        <button
                          onClick={() =>
                            deleteBarber(
                              barber
                            )
                          }
                          className="bg-red-600 text-white px-4 py-2 rounded-xl font-semibold"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </section>

        <section className="bg-white rounded-3xl shadow-lg p-6 border border-rose-200 space-y-4">
          <div>
            <p className="text-sm font-extrabold uppercase tracking-widest text-rose-600 mb-1">
              Menu
            </p>

            <h2 className="text-3xl font-extrabold text-rose-950">
              Services
            </h2>

            <p className="text-gray-600 mt-1">
              Add each service once here. Assign it to individual
              staff members in Shop Setup.
            </p>
          </div>

          {serviceMessage && (
            <div className="bg-green-100 border border-green-200 p-3 rounded-xl font-bold text-green-800">
              {serviceMessage}
            </div>
          )}

          <div className="rounded-2xl bg-rose-50 border border-rose-100 p-4 space-y-3">
            <label className="block font-bold text-rose-950">
              Add service
            </label>

            <input
              type="text"
              value={newServiceName}
              onChange={(event) =>
                setNewServiceName(
                  event.target.value
                )
              }
              placeholder="Service name"
              className="border border-rose-200 bg-white p-3 rounded-xl w-full focus:outline-none focus:ring-2 focus:ring-rose-300"
            />

            <button
              onClick={addService}
              className="bg-rose-700 hover:bg-rose-800 text-white px-5 py-3 rounded-xl font-bold shadow"
            >
              + Add Service
            </button>
          </div>

          <div className="space-y-3">
            {services.length === 0 ? (
              <div className="border border-rose-100 rounded-2xl p-4 bg-rose-50">
                <p className="text-gray-600">
                  No services yet.
                </p>
              </div>
            ) : (
              services.map((service) => (
                <div
                  key={service.id}
                  className="border border-rose-200 rounded-2xl p-4 bg-white shadow-sm"
                >
                  {editingServiceId ===
                  service.id ? (
                    <div className="space-y-3">
                      <input
                        type="text"
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
                        className="border border-rose-200 p-3 rounded-xl w-full focus:outline-none focus:ring-2 focus:ring-rose-300"
                      />

                      <div className="flex gap-2">
                        <button
                          onClick={() =>
                            updateService(
                              service.id
                            )
                          }
                          className="bg-rose-700 text-white px-4 py-2 rounded-xl font-semibold"
                        >
                          Save
                        </button>

                        <button
                          onClick={
                            cancelEditingService
                          }
                          className="bg-gray-200 px-4 py-2 rounded-xl font-semibold"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-3 sm:flex-row sm:justify-between sm:items-center">
                      <div>
                        <p className="text-xl font-extrabold text-rose-950">
                          {service.name}
                        </p>

                        {service.assignment_count >
                          0 && (
                          <p className="text-sm text-gray-600 mt-1">
                            Assigned to{" "}
                            {service.assigned_staff.join(
                              ", "
                            )}
                          </p>
                        )}

                        {!service.assignment_count && (
                          <p className="text-sm text-gray-500 mt-1">
                            Not assigned yet
                          </p>
                        )}
                      </div>

                      <div className="flex gap-2">
                        <button
                          onClick={() =>
                            startEditingService(
                              service
                            )
                          }
                          className="bg-rose-700 text-white px-4 py-2 rounded-xl font-semibold"
                        >
                          Edit
                        </button>

                        {service.assignment_count >
                        0 ? (
                          <button
                            disabled
                            className="bg-gray-300 text-gray-600 px-4 py-2 rounded-xl cursor-not-allowed font-semibold"
                          >
                            In Use
                          </button>
                        ) : (
                          <button
                            onClick={() =>
                              deleteService(
                                service
                              )
                            }
                            className="bg-red-600 text-white px-4 py-2 rounded-xl font-semibold"
                          >
                            Delete
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </section>

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
