"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

const API_BASE = "https://chairtime-production-94da.up.railway.app";

export default function StaffPage() {
  const params = useParams();
  const shopSlug = params.shop;

  const [barbers, setBarbers] = useState([]);
  const [newBarberName, setNewBarberName] = useState("");
  const [editingBarberId, setEditingBarberId] = useState("");
  const [editedBarberName, setEditedBarberName] = useState("");
  const [message, setMessage] = useState("");

  async function loadBarbers() {
    if (!shopSlug) return;

    const response = await fetch(
      `${API_BASE}/api/barbers?shop_slug=${encodeURIComponent(shopSlug)}`
    );

    if (!response.ok) {
      setMessage("Could not load staff.");
      return;
    }

    const data = await response.json();
    setBarbers(data);
  }

  useEffect(() => {
    loadBarbers();
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
      setMessage(error.detail || "Could not add staff member.");
      return;
    }

    setNewBarberName("");
    setMessage("Staff member added.");
    loadBarbers();
  }

  function startEditing(barber) {
    setEditingBarberId(barber.id);
    setEditedBarberName(barber.name);
    setMessage("");
  }

  function cancelEditing() {
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
      setMessage(error.detail || "Could not update staff member.");
      return;
    }

    setEditingBarberId("");
    setEditedBarberName("");
    setMessage("Staff member updated.");
    loadBarbers();
  }

  async function deleteBarber(barber) {
    const confirmed = window.confirm(
      `Delete ${barber.name}?`
    );

    if (!confirmed) return;

    const response = await fetch(
      `${API_BASE}/api/barbers/${encodeURIComponent(barber.id)}`,
      {
        method: "DELETE",
      }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      setMessage(error.detail || "Could not delete staff member.");
      return;
    }

    setMessage("Staff member deleted.");
    loadBarbers();
  }

  return (
    <main className="min-h-screen bg-gray-100 p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="bg-white rounded-3xl shadow-lg p-6 border">
          <h1 className="text-4xl font-bold">Staff</h1>

          <p className="text-gray-700 mt-2">
            Add, rename, or remove service providers.
          </p>

          {message && (
            <div className="mt-4 bg-green-100 p-3 rounded-xl font-bold">
              {message}
            </div>
          )}
        </div>

        <div className="bg-white rounded-3xl shadow-lg p-6 border space-y-4">
          <h2 className="text-2xl font-bold">
            Add Staff Member
          </h2>

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

        <div className="bg-white rounded-3xl shadow-lg p-6 border space-y-3">
          <h2 className="text-2xl font-bold">
            Current Staff
          </h2>

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
                        onClick={cancelEditing}
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
                        {barber.name}
                      </p>
                    </div>

                    <div className="flex gap-2">
                      <button
                        onClick={() =>
                          startEditing(barber)
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
