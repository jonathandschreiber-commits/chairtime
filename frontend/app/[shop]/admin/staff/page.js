"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

const API_BASE = "https://chairtime-production-94da.up.railway.app";

export default function StaffServicesPage() {
  const params = useParams();
  const shopSlug = params.shop;

  const [barbers, setBarbers] = useState([]);
  const [services, setServices] = useState([]);

  const [newBarberName, setNewBarberName] = useState("");
  const [editingBarberId, setEditingBarberId] = useState("");
  const [editedBarberName, setEditedBarberName] = useState("");

  const [newServiceName, setNewServiceName] = useState("");
  const [editingServiceId, setEditingServiceId] = useState("");
  const [editedServiceName, setEditedServiceName] = useState("");

  const [staffMessage, setStaffMessage] = useState("");
  const [serviceMessage, setServiceMessage] = useState("");

  async function loadData() {
    if (!shopSlug) return;

    const [barbersResponse, servicesResponse] = await Promise.all([
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
      setStaffMessage("Could not load staff.");
      return;
    }

    if (!servicesResponse.ok) {
      setServiceMessage("Could not load services.");
      return;
    }

    setBarbers(await barbersResponse.json());
    setServices(await servicesResponse.json());
  }

  useEffect(() => {
    loadData();
  }, [shopSlug]);

  async function addBarber() {
    const cleanName = newBarberName.trim();

    if (!cleanName) {
      setStaffMessage("Enter a staff name.");
      return;
    }

    const existingBarber = barbers[0];

    const response = await fetch(`${API_BASE}/api/barbers`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        name: cleanName,
        shop_name:
          existingBarber?.shop_name || "ChairTime Barbershop",
        phone: "",
        timezone:
          existingBarber?.timezone || "America/New_York",
        shop_slug: shopSlug,
      }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));

      setStaffMessage(
        error.detail || "Could not add staff member."
      );

      return;
    }

    setNewBarberName("");
    setStaffMessage("Staff member added.");
    loadData();
  }

  function startEditingBarber(barber) {
    setEditingBarberId(barber.id);
    setEditedBarberName(barber.name);
    setStaffMessage("");
  }

  function cancelEditingBarber() {
    setEditingBarberId("");
    setEditedBarberName("");
  }

  async function updateBarber(id) {
    const cleanName = editedBarberName.trim();

    if (!cleanName) {
      setStaffMessage("Enter a staff name.");
      return;
    }

    const response = await fetch(
      `${API_BASE}/api/barbers/${encodeURIComponent(id)}`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: cleanName,
        }),
      }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));

      setStaffMessage(
        error.detail || "Could not update staff member."
      );

      return;
    }

    cancelEditingBarber();
    setStaffMessage("Staff member updated.");
    loadData();
  }

  async function deleteBarber(barber) {
    const confirmed = window.confirm(
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
      const error = await response.json().catch(() => ({}));

      setStaffMessage(
        error.detail || "Could not delete staff member."
      );

      return;
    }

    setStaffMessage("Staff member deleted.");
    loadData();
  }

  async function addService() {
    const cleanName = newServiceName.trim();

    if (!cleanName) {
      setServiceMessage("Enter a service name.");
      return;
    }

    const response = await fetch(
      `${API_BASE}/api/service-catalog`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          shop_slug: shopSlug,
          name: cleanName,
        }),
      }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));

      setServiceMessage(
        typeof error.detail === "string"
          ? error.detail
          : "Could not add service."
      );

      return;
    }

    setNewServiceName("");
    setServiceMessage("Service added.");
    loadData();
  }

  function startEditingService(service) {
    setEditingServiceId(service.id);
    setEditedServiceName(service.name);
    setServiceMessage("");
  }

  function cancelEditingService() {
    setEditingServiceId("");
    setEditedServiceName("");
  }

  async function updateService(id) {
    const cleanName = editedServiceName.trim();

    if (!cleanName) {
      setServiceMessage("Enter a service name.");
      return;
    }

    const response = await fetch(
      `${API_BASE}/api/service-catalog/${encodeURIComponent(
        id
      )}`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: cleanName,
        }),
      }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));

      setServiceMessage(
        typeof error.detail === "string"
          ? error.detail
          : "Could not update service."
      );

      return;
    }

    cancelEditingService();
    setServiceMessage("Service updated.");
    loadData();
  }

  async function deleteService(service) {
    const confirmed = window.confirm(
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
      const error = await response.json().catch(() => ({}));

      if (
        error.detail &&
        typeof error.detail === "object"
      ) {
        const staff =
          error.detail.assigned_staff || [];

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
        typeof error.detail === "string"
          ? error.detail
          : "Could not delete service."
      );

      return;
    }

    setServiceMessage("Service deleted.");
    loadData();
  }

  return (
    <main className="min-h-screen bg-gray-100 p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="bg-white rounded-3xl shadow-lg p-6 border">
          <h1 className="text-4xl font-bold">
            Staff & Services
          </h1>

          <p className="text-gray-700 mt-2">
            Manage the shop's staff and master service list.
          </p>
        </div>

        <div className="bg-white rounded-3xl shadow-lg p-6 border space-y-4">
          <h2 className="text-2xl font-bold">
            Staff
          </h2>

          {staffMessage && (
            <div className="bg-green-100 p-3 rounded-xl font-bold">
              {staffMessage}
            </div>
          )}

          <input
            type="text"
            value={newBarberName}
            onChange={(event) =>
              setNewBarberName(event.target.value)
            }
            placeholder="Staff name"
            className="border p-3 rounded-xl w-full"
          />

          <button
            onClick={addBarber}
            className="bg-black text-white px-5 py-3 rounded-xl font-bold"
          >
            Add Staff Member
          </button>

          <div className="space-y-3">
            {barbers.map((barber) => (
              <div
                key={barber.id}
                className="border rounded-2xl p-4"
              >
                {editingBarberId === barber.id ? (
                  <div className="space-y-3">
                    <input
                      type="text"
                      value={editedBarberName}
                      onChange={(event) =>
                        setEditedBarberName(
                          event.target.value
                        )
                      }
                      className="border p-3 rounded-xl w-full"
                    />

                    <div className="flex gap-2">
                      <button
                        onClick={() =>
                          updateBarber(barber.id)
                        }
                        className="bg-black text-white px-4 py-2 rounded-xl"
                      >
                        Save
                      </button>

                      <button
                        onClick={cancelEditingBarber}
                        className="bg-gray-200 px-4 py-2 rounded-xl"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex justify-between items-center gap-4">
                    <p className="text-xl font-bold">
                      {barber.name}
                    </p>

                    <div className="flex gap-2">
                      <button
                        onClick={() =>
                          startEditingBarber(barber)
                        }
                        className="bg-black text-white px-4 py-2 rounded-xl"
                      >
                        Edit
                      </button>

                      <button
                        onClick={() =>
                          deleteBarber(barber)
                        }
                        className="bg-red-600 text-white px-4 py-2 rounded-xl"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-3xl shadow-lg p-6 border space-y-4">
          <h2 className="text-2xl font-bold">
            Services
          </h2>

          <p className="text-gray-600">
            Add each service once here. Assign it to individual
            staff members in Shop Setup.
          </p>

          {serviceMessage && (
            <div className="bg-green-100 p-3 rounded-xl font-bold">
              {serviceMessage}
            </div>
          )}

          <input
            type="text"
            value={newServiceName}
            onChange={(event) =>
              setNewServiceName(event.target.value)
            }
            placeholder="Service name"
            className="border p-3 rounded-xl w-full"
          />

          <button
            onClick={addService}
            className="bg-black text-white px-5 py-3 rounded-xl font-bold"
          >
            Add Service
          </button>

          <div className="space-y-3">
            {services.map((service) => (
              <div
                key={service.id}
                className="border rounded-2xl p-4"
              >
                {editingServiceId === service.id ? (
                  <div className="space-y-3">
                    <input
                      type="text"
                      value={editedServiceName}
                      onChange={(event) =>
                        setEditedServiceName(
                          event.target.value
                        )
                      }
                      className="border p-3 rounded-xl w-full"
                    />

                    <div className="flex gap-2">
                      <button
                        onClick={() =>
                          updateService(service.id)
                        }
                        className="bg-black text-white px-4 py-2 rounded-xl"
                      >
                        Save
                      </button>

                      <button
                        onClick={cancelEditingService}
                        className="bg-gray-200 px-4 py-2 rounded-xl"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex justify-between items-center gap-4">
                    <div>
                      <p className="text-xl font-bold">
                        {service.name}
                      </p>

                      {service.assignment_count > 0 && (
                        <p className="text-sm text-gray-600 mt-1">
                          Assigned to{" "}
                          {service.assigned_staff.join(", ")}
                        </p>
                      )}
                    </div>

                    <div className="flex gap-2">
                      <button
                        onClick={() =>
                          startEditingService(service)
                        }
                        className="bg-black text-white px-4 py-2 rounded-xl"
                      >
                        Edit
                      </button>

                      {service.assignment_count > 0 ? (
                        <button
                          disabled
                          className="bg-gray-300 text-gray-600 px-4 py-2 rounded-xl cursor-not-allowed"
                        >
                          In Use
                        </button>
                      ) : (
                        <button
                          onClick={() =>
                            deleteService(service)
                          }
                          className="bg-red-600 text-white px-4 py-2 rounded-xl"
                        >
                          Delete
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        <a
          href={`/${shopSlug}/admin`}
          className="inline-block font-bold underline"
        >
          Back to Admin
        </a>
      </div>
    </main>
  );
}
