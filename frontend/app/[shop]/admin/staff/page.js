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
  const [teamMembers, setTeamMembers] = useState([]);

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
    staffMessageType,
    setStaffMessageType,
  ] = useState("success");

  const [
    serviceMessage,
    setServiceMessage,
  ] = useState("");

  const [
    accessBarberId,
    setAccessBarberId,
  ] = useState("");

  const [
    accessEmail,
    setAccessEmail,
  ] = useState("");

  const [
    accessPassword,
    setAccessPassword,
  ] = useState("");

  const [
    accessCanAcceptPayments,
    setAccessCanAcceptPayments,
  ] = useState(false);

  const [
    savingAccess,
    setSavingAccess,
  ] = useState(false);

  const [
    teamLoaded,
    setTeamLoaded,
  ] = useState(false);

  const [
    resetPasswordUserId,
    setResetPasswordUserId,
  ] = useState("");

  const [
    resetPassword,
    setResetPassword,
  ] = useState("");

  const [
    resetPasswordConfirm,
    setResetPasswordConfirm,
  ] = useState("");

  const [
    savingResetPassword,
    setSavingResetPassword,
  ] = useState(false);


  function showStaffSuccess(message) {
    setStaffMessageType("success");
    setStaffMessage(message);
  }


  function showStaffError(message) {
    setStaffMessageType("error");
    setStaffMessage(message);
  }


  function clearStaffMessage() {
    setStaffMessage("");
    setStaffMessageType("success");
  }


  function getTeamMemberForBarber(
    barberId
  ) {
    return teamMembers.find(
      (member) =>
        member.barber_id === barberId
    );
  }


  async function loadData() {
    if (!shopSlug) return;

    const [
      barbersResponse,
      servicesResponse,
      teamResponse,
    ] = await Promise.all([
      fetch(
        `${API_BASE}/api/barbers?shop_slug=${encodeURIComponent(
          shopSlug
        )}`,
        {
          cache: "no-store",
        }
      ),

      fetch(
        `${API_BASE}/api/service-catalog?shop_slug=${encodeURIComponent(
          shopSlug
        )}`,
        {
          cache: "no-store",
        }
      ),

      fetch(
        "/api/team",
        {
          method: "GET",
          headers: {
            Accept: "application/json",
          },
          cache: "no-store",
        }
      ),
    ]);

    if (!barbersResponse.ok) {
      showStaffError(
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

    const barbersData =
      await barbersResponse.json();

    const servicesData =
      await servicesResponse.json();

    setBarbers(
      Array.isArray(barbersData)
        ? barbersData
        : []
    );

    setServices(
      Array.isArray(servicesData)
        ? servicesData
        : []
    );

    if (teamResponse.ok) {
      const teamData =
        await teamResponse.json();

      setTeamMembers(
        Array.isArray(teamData.team)
          ? teamData.team
          : []
      );

      setTeamLoaded(true);
    } else {
      setTeamMembers([]);
      setTeamLoaded(false);
    }
  }


  useEffect(() => {
    loadData();
  }, [shopSlug]);


  async function addBarber() {
    const cleanName =
      newBarberName.trim();

    if (!cleanName) {
      showStaffError(
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

      showStaffError(
        error.detail ||
          "Could not add staff member."
      );

      return;
    }

    setNewBarberName("");

    showStaffSuccess(
      "Staff member added."
    );

    await loadData();
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

    setAccessBarberId("");
    cancelResetPassword();
    clearStaffMessage();
  }


  function cancelEditingBarber() {
    setEditingBarberId("");
    setEditedBarberName("");
  }


  async function updateBarber(id) {
    const cleanName =
      editedBarberName.trim();

    if (!cleanName) {
      showStaffError(
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

      showStaffError(
        error.detail ||
          "Could not update staff member."
      );

      return;
    }

    cancelEditingBarber();

    showStaffSuccess(
      "Staff member updated."
    );

    await loadData();
  }


  async function deleteBarber(
    barber
  ) {
    const teamMember =
      getTeamMemberForBarber(
        barber.id
      );

    if (teamMember) {
      showStaffError(
        `${barber.name} has a ChairTime login account. The login account must remain linked to this staff member.`
      );

      return;
    }

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

      showStaffError(
        error.detail ||
          "Could not delete staff member."
      );

      return;
    }

    showStaffSuccess(
      "Staff member deleted."
    );

    await loadData();
  }


  function startGivingAccess(
    barber
  ) {
    setAccessBarberId(
      barber.id
    );

    setEditingBarberId("");
    cancelResetPassword();
    setAccessEmail("");
    setAccessPassword("");
    setAccessCanAcceptPayments(false);
    clearStaffMessage();
  }


  function cancelGivingAccess() {
    setAccessBarberId("");
    setAccessEmail("");
    setAccessPassword("");
    setAccessCanAcceptPayments(false);
  }


  function startResetPassword(
    teamMember
  ) {
    setResetPasswordUserId(
      teamMember.id
    );

    setResetPassword("");
    setResetPasswordConfirm("");
    setEditingBarberId("");
    setAccessBarberId("");
    clearStaffMessage();
  }


  function cancelResetPassword() {
    setResetPasswordUserId("");
    setResetPassword("");
    setResetPasswordConfirm("");
    setSavingResetPassword(false);
  }


  async function saveResetPassword(
    barber,
    teamMember
  ) {
    if (
      resetPassword.length < 8
    ) {
      showStaffError(
        "Temporary password must be at least 8 characters."
      );

      return;
    }

    if (
      resetPassword !==
      resetPasswordConfirm
    ) {
      showStaffError(
        "The passwords do not match."
      );

      return;
    }

    if (savingResetPassword) {
      return;
    }

    setSavingResetPassword(true);
    clearStaffMessage();

    try {
      const response = await fetch(
        `/api/team/${encodeURIComponent(
          teamMember.id
        )}/reset-password`,
        {
          method: "POST",
          headers: {
            Accept:
              "application/json",
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            password:
              resetPassword,
          }),
        }
      );

      const data = await response
        .json()
        .catch(() => ({}));

      if (!response.ok) {
        showStaffError(
          data.detail ||
            data.error ||
            "Could not reset the employee password."
        );

        return;
      }

      cancelResetPassword();

      showStaffSuccess(
        `${barber.name}'s password has been reset.`
      );
    } catch (error) {
      console.error(
        "Reset staff password error:",
        error
      );

      showStaffError(
        "Could not reset the employee password."
      );
    } finally {
      setSavingResetPassword(false);
    }
  }


  async function createLoginAccess(
    barber
  ) {
    const cleanEmail =
      accessEmail.trim().toLowerCase();

    if (!cleanEmail) {
      showStaffError(
        "Enter the employee's email address."
      );

      return;
    }

    if (accessPassword.length < 8) {
      showStaffError(
        "Temporary password must be at least 8 characters."
      );

      return;
    }

    setSavingAccess(true);
    clearStaffMessage();

    try {
      const response = await fetch(
        "/api/team",
        {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            name: barber.name,
            email: cleanEmail,
            password: accessPassword,
            barber_id: barber.id,
            can_accept_payments:
              accessCanAcceptPayments,
          }),
        }
      );

      const data = await response
        .json()
        .catch(() => ({}));

      if (!response.ok) {
        showStaffError(
          data.detail ||
            data.error ||
            "Could not create ChairTime access."
        );

        return;
      }

      cancelGivingAccess();

      showStaffSuccess(
        `${barber.name} now has ChairTime login access.`
      );

      await loadData();
    } catch (error) {
      console.error(
        "Create staff login error:",
        error
      );

      showStaffError(
        "Could not create ChairTime access."
      );
    } finally {
      setSavingAccess(false);
    }
  }

  async function updatePaymentAccess(
    teamMember,
    canAcceptPayments
  ) {
    clearStaffMessage();

    try {
      const response = await fetch(
        `/api/team/${encodeURIComponent(
          teamMember.id
        )}`,
        {
          method: "PATCH",
          headers: {
            Accept: "application/json",
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            can_accept_payments:
              canAcceptPayments,
          }),
        }
      );

      const data = await response
        .json()
        .catch(() => ({}));

      if (!response.ok) {
        showStaffError(
          data.detail ||
            data.error ||
            "Could not update payment access."
        );

        return;
      }

      showStaffSuccess(
        "Employee permissions updated."
      );

      await loadData();
    } catch (error) {
      console.error(
        "Update payment access error:",
        error
      );

      showStaffError(
        "Could not update payment access."
      );
    }
  }


  async function deactivateLogin(
    barber,
    teamMember
  ) {
    const confirmed =
      window.confirm(
        `Disable ChairTime login access for ${barber.name}?`
      );

    if (!confirmed) return;

    clearStaffMessage();

    try {
      const response = await fetch(
        `/api/team/${encodeURIComponent(
          teamMember.id
        )}/deactivate`,
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

      if (!response.ok) {
        showStaffError(
          data.detail ||
            data.error ||
            "Could not disable ChairTime access."
        );

        return;
      }

      showStaffSuccess(
        `${barber.name}'s ChairTime access has been disabled.`
      );

      await loadData();
    } catch (error) {
      console.error(
        "Deactivate staff login error:",
        error
      );

      showStaffError(
        "Could not disable ChairTime access."
      );
    }
  }


  async function activateLogin(
    barber,
    teamMember
  ) {
    clearStaffMessage();

    try {
      const response = await fetch(
        `/api/team/${encodeURIComponent(
          teamMember.id
        )}/activate`,
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

      if (!response.ok) {
        showStaffError(
          data.detail ||
            data.error ||
            "Could not restore ChairTime access."
        );

        return;
      }

      showStaffSuccess(
        `${barber.name}'s ChairTime access has been restored.`
      );

      await loadData();
    } catch (error) {
      console.error(
        "Activate staff login error:",
        error
      );

      showStaffError(
        "Could not restore ChairTime access."
      );
    }
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

    await loadData();
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

    await loadData();
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

    await loadData();
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
                Manage the shop&apos;s staff, login access,
                and master service list.
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
              Add the people who take appointments.
              You can also give individual staff members
              their own ChairTime login.
            </p>
          </div>


          {staffMessage && (
            <div
              className={
                staffMessageType === "error"
                  ? "bg-red-50 border border-red-200 p-3 rounded-xl font-bold text-red-800"
                  : "bg-green-100 border border-green-200 p-3 rounded-xl font-bold text-green-800"
              }
            >
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
              barbers.map((barber) => {
                const teamMember =
                  getTeamMemberForBarber(
                    barber.id
                  );

                const accessIsActive =
                  Boolean(
                    teamMember?.is_active
                  );

                const resettingPassword =
                  Boolean(
                    teamMember &&
                      resetPasswordUserId ===
                        teamMember.id
                  );

                return (
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

                        <div className="flex flex-wrap gap-2">
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
                    ) : accessBarberId ===
                      barber.id ? (
                      <div className="space-y-4">
                        <div>
                          <p className="text-xl font-extrabold text-rose-950">
                            {barber.name}
                          </p>

                          <p className="text-sm text-gray-500">
                            Create ChairTime login access
                          </p>
                        </div>

                        <div className="rounded-2xl border border-blue-100 bg-blue-50 p-4 space-y-4">
                          <div>
                            <label className="block text-sm font-bold text-gray-800 mb-1">
                              Employee email
                            </label>

                            <input
                              type="email"
                              value={
                                accessEmail
                              }
                              onChange={(
                                event
                              ) =>
                                setAccessEmail(
                                  event.target
                                    .value
                                )
                              }
                              placeholder="employee@example.com"
                              autoComplete="off"
                              className="border border-blue-200 bg-white p-3 rounded-xl w-full focus:outline-none focus:ring-2 focus:ring-blue-300"
                            />
                          </div>

                          <div>
                            <label className="block text-sm font-bold text-gray-800 mb-1">
                              Temporary password
                            </label>

                            <input
                              type="password"
                              value={
                                accessPassword
                              }
                              onChange={(
                                event
                              ) =>
                                setAccessPassword(
                                  event.target
                                    .value
                                )
                              }
                              placeholder="At least 8 characters"
                              autoComplete="new-password"
                              className="border border-blue-200 bg-white p-3 rounded-xl w-full focus:outline-none focus:ring-2 focus:ring-blue-300"
                            />

                            <p className="text-xs text-gray-500 mt-1">
                              Give this password to the employee
                              so they can sign in.
                            </p>
                          </div>

                          <label className="flex items-start gap-3 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={
                                accessCanAcceptPayments
                              }
                              onChange={(
                                event
                              ) =>
                                setAccessCanAcceptPayments(
                                  event.target
                                    .checked
                                )
                              }
                              className="mt-1 h-4 w-4"
                            />

                            <span>
                              <span className="block font-bold text-gray-900">
                                Allow this employee to charge customers
                              </span>

                              <span className="block text-sm text-gray-600">
                                The payment will go to the shop&apos;s
                                connected payment account.
                              </span>
                            </span>
                          </label>

                          <div className="flex flex-wrap gap-2">
                            <button
                              onClick={() =>
                                createLoginAccess(
                                  barber
                                )
                              }
                              disabled={
                                savingAccess
                              }
                              className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white px-4 py-2 rounded-xl font-semibold"
                            >
                              {savingAccess
                                ? "Creating..."
                                : "Create Login"}
                            </button>

                            <button
                              onClick={
                                cancelGivingAccess
                              }
                              disabled={
                                savingAccess
                              }
                              className="bg-gray-200 px-4 py-2 rounded-xl font-semibold"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      </div>

                    ) : resettingPassword ? (
                      <div className="space-y-4">
                        <div>
                          <p className="text-xl font-extrabold text-rose-950">
                            {barber.name}
                          </p>

                          <p className="text-sm text-gray-500">
                            Reset employee password
                          </p>
                        </div>

                        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 space-y-4">
                          <div>
                            <label className="block text-sm font-bold text-gray-800 mb-1">
                              New temporary password
                            </label>

                            <input
                              type="password"
                              value={
                                resetPassword
                              }
                              onChange={(
                                event
                              ) =>
                                setResetPassword(
                                  event.target
                                    .value
                                )
                              }
                              placeholder="At least 8 characters"
                              autoComplete="new-password"
                              className="border border-amber-200 bg-white p-3 rounded-xl w-full focus:outline-none focus:ring-2 focus:ring-amber-300"
                            />
                          </div>

                          <div>
                            <label className="block text-sm font-bold text-gray-800 mb-1">
                              Confirm temporary password
                            </label>

                            <input
                              type="password"
                              value={
                                resetPasswordConfirm
                              }
                              onChange={(
                                event
                              ) =>
                                setResetPasswordConfirm(
                                  event.target
                                    .value
                                )
                              }
                              placeholder="Enter it again"
                              autoComplete="new-password"
                              className="border border-amber-200 bg-white p-3 rounded-xl w-full focus:outline-none focus:ring-2 focus:ring-amber-300"
                            />
                          </div>

                          <p className="text-sm text-gray-600">
                            The employee&apos;s existing password
                            will stop working immediately. Give the
                            employee this temporary password so they
                            can sign in.
                          </p>

                          <div className="flex flex-wrap gap-2">
                            <button
                              onClick={() =>
                                saveResetPassword(
                                  barber,
                                  teamMember
                                )
                              }
                              disabled={
                                savingResetPassword
                              }
                              className="bg-amber-600 hover:bg-amber-700 disabled:bg-amber-300 text-white px-4 py-2 rounded-xl font-semibold"
                            >
                              {savingResetPassword
                                ? "Resetting..."
                                : "Reset Password"}
                            </button>

                            <button
                              onClick={
                                cancelResetPassword
                              }
                              disabled={
                                savingResetPassword
                              }
                              className="bg-gray-200 px-4 py-2 rounded-xl font-semibold"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-4">
                        <div className="flex flex-col gap-3 sm:flex-row sm:justify-between sm:items-start">
                          <div>
                            <p className="text-xl font-extrabold text-rose-950">
                              {barber.name}
                            </p>

                            <p className="text-sm text-gray-500">
                              Staff member
                            </p>

                            {teamLoaded &&
                              !teamMember && (
                                <div className="mt-2">
                                  <span className="inline-flex items-center rounded-full bg-gray-100 px-3 py-1 text-xs font-bold text-gray-700">
                                    ChairTime access: Not enabled
                                  </span>
                                </div>
                              )}

                            {teamMember &&
                              accessIsActive && (
                                <div className="mt-2 space-y-1">
                                  <span className="inline-flex items-center rounded-full bg-green-100 px-3 py-1 text-xs font-bold text-green-800">
                                    ChairTime access: Active
                                  </span>

                                  <p className="text-sm text-gray-600">
                                    {teamMember.email}
                                  </p>
                                </div>
                              )}

                            {teamMember &&
                              !accessIsActive && (
                                <div className="mt-2 space-y-1">
                                  <span className="inline-flex items-center rounded-full bg-amber-100 px-3 py-1 text-xs font-bold text-amber-800">
                                    ChairTime access: Disabled
                                  </span>

                                  <p className="text-sm text-gray-600">
                                    {teamMember.email}
                                  </p>
                                </div>
                              )}
                          </div>

                          <div className="flex flex-wrap gap-2">
                            {teamLoaded &&
                              !teamMember && (
                                <button
                                  onClick={() =>
                                    startGivingAccess(
                                      barber
                                    )
                                  }
                                  className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-xl font-semibold"
                                >
                                  Give Login Access
                                </button>
                              )}

                            {teamMember &&
                              accessIsActive && (
                                <>
                                  <button
                                    onClick={() =>
                                      startResetPassword(
                                        teamMember
                                      )
                                    }
                                    className="bg-amber-600 hover:bg-amber-700 text-white px-4 py-2 rounded-xl font-semibold"
                                  >
                                    Reset Password
                                  </button>

                                  <button
                                    onClick={() =>
                                      deactivateLogin(
                                        barber,
                                        teamMember
                                      )
                                    }
                                    className="bg-gray-700 hover:bg-gray-800 text-white px-4 py-2 rounded-xl font-semibold"
                                  >
                                    Disable Access
                                  </button>
                                </>
                              )}

                            {teamMember &&
                              !accessIsActive && (
                                <button
                                  onClick={() =>
                                    activateLogin(
                                      barber,
                                      teamMember
                                    )
                                  }
                                  className="bg-green-700 hover:bg-green-800 text-white px-4 py-2 rounded-xl font-semibold"
                                >
                                  Restore Access
                                </button>
                              )}

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

                            {!teamMember && (
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
                            )}
                          </div>
                        </div>


                        {teamMember && (
                          <div className="rounded-xl border border-gray-200 bg-gray-50 p-3">
                            <label className="flex items-start gap-3">
                              <input
                                type="checkbox"
                                checked={
                                  Boolean(
                                    teamMember.can_accept_payments
                                  )
                                }
                                disabled={
                                  !accessIsActive
                                }
                                onChange={(
                                  event
                                ) =>
                                  updatePaymentAccess(
                                    teamMember,
                                    event.target
                                      .checked
                                  )
                                }
                                className="mt-1 h-4 w-4"
                              />

                              <span>
                                <span className="block text-sm font-bold text-gray-900">
                                  Can charge customers
                                </span>

                                <span className="block text-xs text-gray-600">
                                  Allows this employee to collect
                                  customer payments through ChairTime.
                                </span>
                              </span>
                            </label>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })
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
