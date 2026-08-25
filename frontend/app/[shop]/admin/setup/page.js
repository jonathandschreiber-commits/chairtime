"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

const API_BASE = "https://chairtime-production-94da.up.railway.app";

const WEEKDAY_NAMES = {
  0: "Monday",
  1: "Tuesday",
  2: "Wednesday",
  3: "Thursday",
  4: "Friday",
  5: "Saturday",
  6: "Sunday",
};

const WEEKDAY_MAP = {
  Monday: 0,
  Tuesday: 1,
  Wednesday: 2,
  Thursday: 3,
  Friday: 4,
  Saturday: 5,
  Sunday: 6,
};

export default function SetupPage() {
  const params = useParams();
  const shopSlug = params.shop;

  const [barbers, setBarbers] = useState([]);
  const [services, setServices] = useState([]);
  const [serviceCatalog, setServiceCatalog] = useState([]);
  const [blockedTimes, setBlockedTimes] = useState([]);
  const [availabilityRules, setAvailabilityRules] = useState([]);

  const [serviceBarberId, setServiceBarberId] = useState("");
  const [serviceName, setServiceName] = useState("");
  const [serviceDuration, setServiceDuration] = useState("30");
  const [servicePrice, setServicePrice] = useState("");

  const [editingServiceId, setEditingServiceId] = useState("");
  const [editedServiceName, setEditedServiceName] = useState("");
  const [editedServiceDuration, setEditedServiceDuration] = useState("");
  const [editedServicePrice, setEditedServicePrice] = useState("");

  const [availabilityBarberId, setAvailabilityBarberId] = useState("");
  const [availabilityDay, setAvailabilityDay] = useState("Monday");
  const [availabilityStart, setAvailabilityStart] = useState("09:00");
  const [availabilityEnd, setAvailabilityEnd] = useState("17:00");

  const [blockBarberId, setBlockBarberId] = useState("");
  const [blockReason, setBlockReason] = useState("Lunch");
  const [blockStart, setBlockStart] = useState("");
  const [blockEnd, setBlockEnd] = useState("");

  const [fullDayDate, setFullDayDate] = useState(
    new Date().toISOString().slice(0, 10)
  );

  const [message, setMessage] = useState("");

  async function loadData() {
    if (!shopSlug) return;

    const query =
      "?shop_slug=" + encodeURIComponent(shopSlug);

    try {
      const [
        barbersRes,
        servicesRes,
        catalogRes,
        blockedRes,
        availabilityRes,
      ] = await Promise.all([
        fetch(`${API_BASE}/api/barbers${query}`),
        fetch(`${API_BASE}/api/services${query}`),
        fetch(`${API_BASE}/api/service-catalog${query}`),
        fetch(`${API_BASE}/api/blocked-times${query}`),
        fetch(`${API_BASE}/api/availability-rules${query}`),
      ]);

      if (
        !barbersRes.ok ||
        !servicesRes.ok ||
        !catalogRes.ok ||
        !blockedRes.ok ||
        !availabilityRes.ok
      ) {
        setMessage("Could not load shop setup.");
        return;
      }

      const barbersData = await barbersRes.json();
      const servicesData = await servicesRes.json();
      const catalogData = await catalogRes.json();
      const blockedData = await blockedRes.json();
      const availabilityData =
        await availabilityRes.json();

      setBarbers(barbersData);
      setServices(servicesData);
      setServiceCatalog(catalogData);
      setBlockedTimes(blockedData);
      setAvailabilityRules(availabilityData);

      if (barbersData.length > 0) {
        setServiceBarberId(
          (current) => current || barbersData[0].id
        );

        setAvailabilityBarberId(
          (current) => current || barbersData[0].id
        );

        setBlockBarberId(
          (current) => current || barbersData[0].id
        );
      }
    } catch (error) {
      console.error(error);
      setMessage("Could not load shop setup.");
    }
  }

  useEffect(() => {
    if (shopSlug) {
      loadData();
    }
  }, [shopSlug]);

  function formatTime(value) {
    if (!value) return "";
    return String(value).slice(0, 5);
  }

  function isFullDay(block) {
    return (
      block.start_datetime?.endsWith("T00:00:00") &&
      block.end_datetime?.endsWith("T23:59:00")
    );
  }

  async function addService() {
    const duration = Number(serviceDuration);
    const price = Number(servicePrice);

    if (!serviceBarberId) {
      setMessage("Choose a staff member.");
      return;
    }

    if (!serviceName) {
      setMessage("Choose a service.");
      return;
    }

    if (!duration || duration <= 0) {
      setMessage("Enter a valid duration.");
      return;
    }

    if (
      servicePrice === "" ||
      Number.isNaN(price) ||
      price < 0
    ) {
      setMessage("Enter a valid price.");
      return;
    }

    const response = await fetch(
      `${API_BASE}/api/services`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          shop_slug: shopSlug,
          barber_id: serviceBarberId,
          name: serviceName,
          duration_minutes: duration,
          price,
        }),
      }
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({}));

      setMessage(
        typeof error.detail === "string"
          ? error.detail
          : "Could not assign service."
      );

      return;
    }

    setServiceName("");
    setServiceDuration("30");
    setServicePrice("");
    setMessage("Service assigned.");

    loadData();
  }

  function startEditingService(service) {
    setEditingServiceId(service.id);
    setEditedServiceName(service.name);

    setEditedServiceDuration(
      String(service.duration_minutes)
    );

    setEditedServicePrice(
      String(service.price)
    );

    setMessage("");
  }

  function cancelEditingService() {
    setEditingServiceId("");
    setEditedServiceName("");
    setEditedServiceDuration("");
    setEditedServicePrice("");
  }

  async function updateService(serviceId) {
    const duration = Number(
      editedServiceDuration
    );

    const price = Number(
      editedServicePrice
    );

    if (!editedServiceName) {
      setMessage("Choose a service.");
      return;
    }

    if (!duration || duration <= 0) {
      setMessage("Enter a valid duration.");
      return;
    }

    if (
      editedServicePrice === "" ||
      Number.isNaN(price) ||
      price < 0
    ) {
      setMessage("Enter a valid price.");
      return;
    }

    const response = await fetch(
      `${API_BASE}/api/services/${encodeURIComponent(
        serviceId
      )}`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: editedServiceName,
          duration_minutes: duration,
          price,
        }),
      }
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({}));

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
      `Remove ${service.name} from this staff member?`
    );

    if (!confirmed) return;

    const response = await fetch(
      `${API_BASE}/api/services/${encodeURIComponent(
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

      setMessage(
        error.detail ||
          "Could not remove service."
      );

      return;
    }

    setMessage(
      "Service removed from staff member."
    );

    loadData();
  }

  async function addAvailabilityRule() {
    if (!availabilityBarberId) {
      setMessage("Choose a staff member.");
      return;
    }

    if (
      !availabilityStart ||
      !availabilityEnd
    ) {
      setMessage(
        "Enter start and end times."
      );
      return;
    }

    if (
      availabilityStart >= availabilityEnd
    ) {
      setMessage(
        "End time must be later than start time."
      );
      return;
    }

    const response = await fetch(
      `${API_BASE}/api/availability-rules`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          shop_slug: shopSlug,
          barber_id: availabilityBarberId,
          weekday:
            WEEKDAY_MAP[availabilityDay],
          start_time: `${availabilityStart}:00`,
          end_time: `${availabilityEnd}:00`,
        }),
      }
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({}));

      setMessage(
        error.detail ||
          "Could not save availability."
      );

      return;
    }

    setMessage(
      "Weekly availability saved."
    );

    loadData();
  }

  async function deleteAvailabilityRule(id) {
    const response = await fetch(
      `${API_BASE}/api/availability-rules/${encodeURIComponent(
        id
      )}`,
      {
        method: "DELETE",
      }
    );

    if (!response.ok) {
      setMessage(
        "Could not delete availability."
      );
      return;
    }

    setMessage(
      "Weekly availability deleted."
    );

    loadData();
  }

  async function blockTime() {
    if (!blockBarberId) {
      setMessage("Choose a staff member.");
      return;
    }

    if (!blockStart || !blockEnd) {
      setMessage(
        "Enter the start and end of the blocked time."
      );
      return;
    }

    if (blockStart >= blockEnd) {
      setMessage(
        "End time must be later than start time."
      );
      return;
    }

    const response = await fetch(
      `${API_BASE}/api/blocked-times`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          shop_slug: shopSlug,
          barber_id: blockBarberId,
          reason:
            blockReason.trim() || "Blocked",
          start_datetime: blockStart,
          end_datetime: blockEnd,
        }),
      }
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({}));

      setMessage(
        error.detail ||
          "Could not block time."
      );

      return;
    }

    setBlockReason("Lunch");
    setBlockStart("");
    setBlockEnd("");
    setMessage("Time blocked.");

    loadData();
  }

  async function blockFullDay(reason) {
    if (!blockBarberId || !fullDayDate) {
      setMessage(
        "Choose a staff member and date."
      );
      return;
    }

    const response = await fetch(
      `${API_BASE}/api/blocked-times`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          shop_slug: shopSlug,
          barber_id: blockBarberId,
          reason,
          start_datetime:
            `${fullDayDate}T00:00:00`,
          end_datetime:
            `${fullDayDate}T23:59:00`,
        }),
      }
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({}));

      setMessage(
        error.detail ||
          "Could not block full day."
      );

      return;
    }

    setMessage(
      `${reason} full day blocked.`
    );

    loadData();
  }

  async function deleteBlockedTime(id) {
    const response = await fetch(
      `${API_BASE}/api/blocked-times/${encodeURIComponent(
        id
      )}`,
      {
        method: "DELETE",
      }
    );

    if (!response.ok) {
      setMessage(
        "Could not remove blocked time."
      );
      return;
    }

    setMessage(
      "Blocked time removed."
    );

    loadData();
  }

  const selectedBarberServices =
    useMemo(() => {
      return services
        .filter(
          (service) =>
            service.barber_id ===
            serviceBarberId
        )
        .sort((a, b) =>
          String(a.name).localeCompare(
            String(b.name)
          )
        );
    }, [services, serviceBarberId]);

  const availableCatalogServices =
    useMemo(() => {
      const assignedNames = new Set(
        selectedBarberServices.map(
          (service) =>
            String(service.name).toLowerCase()
        )
      );

      return serviceCatalog
        .filter(
          (service) =>
            !assignedNames.has(
              String(
                service.name
              ).toLowerCase()
            )
        )
        .sort((a, b) =>
          String(a.name).localeCompare(
            String(b.name)
          )
        );
    }, [
      serviceCatalog,
      selectedBarberServices,
    ]);

  const selectedBarberAvailability =
    useMemo(() => {
      return availabilityRules
        .filter(
          (rule) =>
            rule.barber_id ===
            availabilityBarberId
        )
        .sort((a, b) => {
          if (
            a.weekday !== b.weekday
          ) {
            return (
              a.weekday - b.weekday
            );
          }

          return String(
            a.start_time
          ).localeCompare(
            String(b.start_time)
          );
        });
    }, [
      availabilityRules,
      availabilityBarberId,
    ]);

  const selectedBarberBlockedTimes =
    useMemo(() => {
      const now = new Date();

      return blockedTimes
        .filter(
          (block) =>
            block.barber_id ===
              blockBarberId &&
            new Date(
              block.end_datetime
            ) >= now
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
    }, [
      blockedTimes,
      blockBarberId,
    ]);

  return (
    <main className="min-h-screen bg-gray-100 p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        <h1 className="text-4xl font-bold">
          {shopSlug} Shop Setup
        </h1>

        {message && (
          <div className="bg-green-100 p-3 rounded-xl font-bold">
            {message}
          </div>
        )}

        <div className="bg-white p-6 rounded-2xl shadow space-y-4">
          <h2 className="text-2xl font-bold">
            Services
          </h2>

          <p className="text-gray-600">
            Choose a staff member, then assign
            services from the shop's master
            service list.
          </p>

          <select
            value={serviceBarberId}
            onChange={(event) => {
              setServiceBarberId(
                event.target.value
              );

              setServiceName("");
              cancelEditingService();
            }}
            className="border p-3 rounded w-full"
          >
            {barbers.map((barber) => (
              <option
                key={barber.id}
                value={barber.id}
              >
                {barber.name}
              </option>
            ))}
          </select>

          <select
            value={serviceName}
            onChange={(event) =>
              setServiceName(
                event.target.value
              )
            }
            className="border p-3 rounded w-full"
          >
            <option value="">
              Choose service
            </option>

            {availableCatalogServices.map(
              (service) => (
                <option
                  key={service.id}
                  value={service.name}
                >
                  {service.name}
                </option>
              )
            )}
          </select>

          {availableCatalogServices.length ===
            0 && (
            <p className="text-sm text-gray-500">
              All shop services are already
              assigned to this staff member.
            </p>
          )}

          <input
            type="number"
            min="1"
            placeholder="Duration in minutes"
            value={serviceDuration}
            onChange={(event) =>
              setServiceDuration(
                event.target.value
              )
            }
            className="border p-3 rounded w-full"
          />

          <input
            type="number"
            min="0"
            step="0.01"
            placeholder="Price"
            value={servicePrice}
            onChange={(event) =>
              setServicePrice(
                event.target.value
              )
            }
            className="border p-3 rounded w-full"
          />

          <button
            onClick={addService}
            disabled={
              !serviceName ||
              !serviceBarberId
            }
            className={`px-4 py-3 rounded-xl font-bold ${
              !serviceName ||
              !serviceBarberId
                ? "bg-gray-300 text-gray-600 cursor-not-allowed"
                : "bg-black text-white"
            }`}
          >
            Assign Service
          </button>

          <div className="space-y-2">
            {selectedBarberServices.length ===
            0 ? (
              <p className="text-gray-500">
                No services for this staff
                member.
              </p>
            ) : (
              selectedBarberServices.map(
                (service) => (
                  <div
                    key={service.id}
                    className="border rounded-xl p-4"
                  >
                    {editingServiceId ===
                    service.id ? (
                      <div className="space-y-3">
                        <select
                          value={
                            editedServiceName
                          }
                          onChange={(event) =>
                            setEditedServiceName(
                              event.target.value
                            )
                          }
                          className="border p-3 rounded w-full"
                        >
                          {serviceCatalog.map(
                            (
                              catalogService
                            ) => (
                              <option
                                key={
                                  catalogService.id
                                }
                                value={
                                  catalogService.name
                                }
                              >
                                {
                                  catalogService.name
                                }
                              </option>
                            )
                          )}
                        </select>

                        <input
                          type="number"
                          min="1"
                          value={
                            editedServiceDuration
                          }
                          onChange={(
                            event
                          ) =>
                            setEditedServiceDuration(
                              event.target
                                .value
                            )
                          }
                          className="border p-3 rounded w-full"
                          placeholder="Duration in minutes"
                        />

                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          value={
                            editedServicePrice
                          }
                          onChange={(
                            event
                          ) =>
                            setEditedServicePrice(
                              event.target
                                .value
                            )
                          }
                          className="border p-3 rounded w-full"
                          placeholder="Price"
                        />

                        <div className="flex gap-2">
                          <button
                            onClick={() =>
                              updateService(
                                service.id
                              )
                            }
                            className="bg-black text-white px-4 py-2 rounded-xl"
                          >
                            Save
                          </button>

                          <button
                            onClick={
                              cancelEditingService
                            }
                            className="bg-gray-200 px-4 py-2 rounded-xl"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex justify-between items-center gap-4">
                        <div>
                          <p className="font-bold">
                            {
                              service.name
                            }
                          </p>

                          <p className="text-sm text-gray-600">
                            {
                              service.duration_minutes
                            }{" "}
                            minutes · $
                            {Number(
                              service.price
                            ).toFixed(2)}
                          </p>
                        </div>

                        <div className="flex gap-2">
                          <button
                            onClick={() =>
                              startEditingService(
                                service
                              )
                            }
                            className="bg-black text-white px-3 py-2 rounded"
                          >
                            Edit
                          </button>

                          <button
                            onClick={() =>
                              deleteService(
                                service
                              )
                            }
                            className="bg-red-500 text-white px-3 py-2 rounded"
                          >
                            Remove
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )
              )
            )}
          </div>
        </div>

        <div className="bg-white p-6 rounded-2xl shadow space-y-4">
          <h2 className="text-2xl font-bold">
            Weekly Availability
          </h2>

          <select
            value={availabilityBarberId}
            onChange={(event) =>
              setAvailabilityBarberId(
                event.target.value
              )
            }
            className="border p-3 rounded w-full"
          >
            {barbers.map((barber) => (
              <option
                key={barber.id}
                value={barber.id}
              >
                {barber.name}
              </option>
            ))}
          </select>

          <select
            value={availabilityDay}
            onChange={(event) =>
              setAvailabilityDay(
                event.target.value
              )
            }
            className="border p-3 rounded w-full"
          >
            {Object.keys(
              WEEKDAY_MAP
            ).map((day) => (
              <option
                key={day}
                value={day}
              >
                {day}
              </option>
            ))}
          </select>

          <input
            type="time"
            value={availabilityStart}
            onChange={(event) =>
              setAvailabilityStart(
                event.target.value
              )
            }
            className="border p-3 rounded w-full"
          />

          <input
            type="time"
            value={availabilityEnd}
            onChange={(event) =>
              setAvailabilityEnd(
                event.target.value
              )
            }
            className="border p-3 rounded w-full"
          />

          <button
            onClick={addAvailabilityRule}
            className="bg-black text-white px-4 py-3 rounded-xl"
          >
            Save Availability
          </button>

          <div className="space-y-2">
            {selectedBarberAvailability.length ===
            0 ? (
              <p className="text-gray-500">
                No weekly availability for
                this staff member.
              </p>
            ) : (
              selectedBarberAvailability.map(
                (rule) => (
                  <div
                    key={rule.id}
                    className="border rounded-xl p-3 flex justify-between items-center"
                  >
                    <div>
                      {
                        WEEKDAY_NAMES[
                          rule.weekday
                        ]
                      }{" "}
                      ·{" "}
                      {formatTime(
                        rule.start_time
                      )}{" "}
                      -{" "}
                      {formatTime(
                        rule.end_time
                      )}
                    </div>

                    <button
                      onClick={() =>
                        deleteAvailabilityRule(
                          rule.id
                        )
                      }
                      className="bg-red-500 text-white px-3 py-1 rounded"
                    >
                      Delete
                    </button>
                  </div>
                )
              )
            )}
          </div>
        </div>

        <div className="bg-white p-6 rounded-2xl shadow space-y-4">
          <h2 className="text-2xl font-bold">
            Quick Block Time
          </h2>

          <select
            value={blockBarberId}
            onChange={(event) =>
              setBlockBarberId(
                event.target.value
              )
            }
            className="border p-3 rounded w-full"
          >
            {barbers.map((barber) => (
              <option
                key={barber.id}
                value={barber.id}
              >
                {barber.name}
              </option>
            ))}
          </select>

          <input
            value={blockReason}
            onChange={(event) =>
              setBlockReason(
                event.target.value
              )
            }
            placeholder="Reason"
            className="border p-3 rounded w-full"
          />

          <input
            type="datetime-local"
            value={blockStart}
            onChange={(event) =>
              setBlockStart(
                event.target.value
              )
            }
            className="border p-3 rounded w-full"
          />

          <input
            type="datetime-local"
            value={blockEnd}
            onChange={(event) =>
              setBlockEnd(
                event.target.value
              )
            }
            className="border p-3 rounded w-full"
          />

          <button
            onClick={blockTime}
            className="bg-black text-white px-4 py-3 rounded-xl"
          >
            Block Time
          </button>
        </div>

        <div className="bg-white p-6 rounded-2xl shadow space-y-4">
          <h2 className="text-2xl font-bold">
            Full Day Block
          </h2>

          <select
            value={blockBarberId}
            onChange={(event) =>
              setBlockBarberId(
                event.target.value
              )
            }
            className="border p-3 rounded w-full"
          >
            {barbers.map((barber) => (
              <option
                key={barber.id}
                value={barber.id}
              >
                {barber.name}
              </option>
            ))}
          </select>

          <input
            type="date"
            value={fullDayDate}
            onChange={(event) =>
              setFullDayDate(
                event.target.value
              )
            }
            className="border p-3 rounded w-full"
          />

          <div className="flex gap-3">
            <button
              onClick={() =>
                blockFullDay("Vacation")
              }
              className="bg-black text-white px-4 py-3 rounded-xl"
            >
              Vacation
            </button>

            <button
              onClick={() =>
                blockFullDay("Closed")
              }
              className="bg-red-600 text-white px-4 py-3 rounded-xl"
            >
              Closed
            </button>
          </div>

          <div className="space-y-2">
            {selectedBarberBlockedTimes.length ===
            0 ? (
              <p className="text-gray-500">
                No upcoming blocked times for
                this staff member.
              </p>
            ) : (
              selectedBarberBlockedTimes.map(
                (block) => (
                  <div
                    key={block.id}
                    className="border rounded-xl p-3 flex justify-between items-center"
                  >
                    <div>
                      {block.reason} ·{" "}
                      {isFullDay(block)
                        ? new Date(
                            block.start_datetime
                          ).toLocaleDateString()
                        : new Date(
                            block.start_datetime
                          ).toLocaleString()}
                    </div>

                    <button
                      onClick={() =>
                        deleteBlockedTime(
                          block.id
                        )
                      }
                      className="bg-red-500 text-white px-3 py-1 rounded"
                    >
                      Delete
                    </button>
                  </div>
                )
              )
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
