"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export default function AdminUserBar() {
  const router = useRouter();

  const [currentUser, setCurrentUser] =
    useState(null);

  const [loggingOut, setLoggingOut] =
    useState(false);

  useEffect(() => {
    let active = true;

    async function loadCurrentUser() {
      try {
        const response = await fetch(
          "/api/auth/me",
          {
            method: "GET",
            cache: "no-store",
          }
        );

        if (response.status === 401) {
          router.replace("/login");
          return;
        }

        if (!response.ok) {
          return;
        }

        const data = await response.json();

        if (active) {
          setCurrentUser(data);
        }
      } catch (error) {
        console.error(
          "Could not load current user:",
          error
        );
      }
    }

    loadCurrentUser();

    return () => {
      active = false;
    };
  }, [router]);

  async function handleLogout() {
    if (loggingOut) {
      return;
    }

    setLoggingOut(true);

    try {
      await fetch("/api/auth/logout", {
        method: "POST",
      });
    } catch (error) {
      console.error(
        "Logout request failed:",
        error
      );
    } finally {
      router.replace("/login");
      router.refresh();
    }
  }

  const role = String(
    currentUser?.role || ""
  )
    .trim()
    .toLowerCase();

  const roleLabel =
    role === "owner"
      ? "Owner"
      : role === "staff"
        ? "Staff"
        : "";

  return (
    <div className="flex flex-wrap items-center justify-end gap-3">
      {currentUser && (
        <div className="text-right">
          <p className="font-bold text-gray-900">
            {currentUser.name}
          </p>

          {roleLabel && (
            <p className="text-sm text-gray-600">
              {roleLabel}
            </p>
          )}
        </div>
      )}

      <button
        type="button"
        onClick={handleLogout}
        disabled={loggingOut}
        className="rounded-xl bg-gray-900 px-4 py-2 font-bold text-white hover:bg-gray-700 disabled:opacity-60"
      >
        {loggingOut
          ? "Logging Out..."
          : "Log Out"}
      </button>
    </div>
  );
}
