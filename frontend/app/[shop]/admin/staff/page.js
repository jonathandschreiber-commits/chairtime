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

  const [message, setMessage] = useState("");

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
      setMessage("Could not load staff.");
      return;
    }

    if (!servicesResponse.ok) {
      setMessage("Could not load services.");
      return;
    }

    const barbersData = await barbersResponse.json();
    const servicesData = await servicesResponse.json();

    setBarbers(barbersData);
    setServices(servicesData);
  }

  useEffect(() => {
    loadData();
  }, [shopSlug]);

  async function addBarber() {
    const cleanName = newBarberName.trim();

    if (!cleanName) {
      setMessage("Enter a staff name.");
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
      setMessage(
        error.detail || "Could not add staff member."
      );
      return;
    }

    setNewBarberName("");
    setMessage("Staff member added.");
    loadData();
  }

  function startEditingBarber(barber) {
    setEditingBarberId(barber.id);
    setEditedBarberName(barber.name);
    setMessage("");
  }

  function cancelEditingBarber() {
    setEditingBarberId("");
    setEditedBarberName("");
  }

  async function updateBarber(id) {
    const cleanName = editedBarberName.trim();

    if (!cleanName) {
      setMessage("Enter a staff name.");
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
      setMessage(
        error.detail || "Could not update staff member."
      );
      return;
    }

    cancelEditingBarber();
    setMessage("Staff member updated.");
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
      setMessage(
        error.detail || "Could not delete staff member."
      );
      return;
    }

    setMessage("Staff member deleted.");
    loadData();
  }

  async function addService() {
    const cleanName = newServiceName.trim();

    if (!cleanName) {
      setMessage("Enter a service name.");
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
      setMessage(
        typeof error.detail === "string"
          ? error.detail
          : "Could not add service."
      );
      return;
    }

    setNewServiceName("");
    setMessage("Service added.");
    loadData();
  }

  function startEditingService(service) {
    setEditingServiceId(service.id);
    setEditedServiceName(service.name);
    setMessage("");
  }

  function cancelEditingService() {
    setEditingServiceId("");
    setEditedServiceName("");
  }

  async function updateService(id) {
    const cleanName = editedServiceName.trim();

    if (!cleanName) {
      setMessage("Enter a service name.");
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
      setMessage(
        typeof error.detail === "string"
          ? error.detail
          : "Could not update service."
      );
      return;
    }

    cancelEditingService();
    setMessage("Service updated.");
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

      setMessage(
        typeof error.detail === "string"
          ? error.detail
          : "Could not delete service."
      );

      return;
    }

    setMessage("Service deleted.");
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

          {message && (
            <div className="mt-4 bg-green-100 p-3 rounded-xl font-bold">
              {message}
            </div>
          )}
        </div>

        <div className="bg-white rounded-3xl shadow-lg p-6 border space-y-4">
          <h2 className="text-2xl font-bold">
            Staff
          </h2>

          <div className="space-y-3">
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
          </div>

          <div className="space-y-3">
            {barbers.length === 0 ? (
              <p className="text-gray-500">
                No staff members found.
              </p>
            ) : (
              barbers.map((barber) => (
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
              ))
            )}
          </div>
        </div>

        <div className="bg-white rounded-3xl shadow-lg p-6 border space-y-4">
          <h2 className="text-2xl font-bold">
            Services
          </h2>

          <p className="text-gray-600">
            These are the services offered by the shop.
            Staff members are assigned to them in Shop Setup.
          </p>

          <div className="space-y-3">
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
          </div>

          <div className="space-y-3">
            {services.length === 0 ? (
              <p className="text-gray-500">
                No services found.
              </p>
            ) : (
              services.map((service) => (
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
                      <p className="text-xl font-bold">
                        {service.name}
                      </p>

                      <div className="flex gap-2">
                        <button
                          onClick={() =>
                            startEditingService(service)
                          }
                          className="bg-black text-white px-4 py-2 rounded-xl"
                        >
                          Edit
                        </button>

                        <button
                          onClick={() =>
                            deleteService(service)
                          }
                          className="bg-red-600 text-white px-4 py-2 rounded-xl"
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
