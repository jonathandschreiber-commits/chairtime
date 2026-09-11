"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

export default function AIReceptionistPage() {
  const params = useParams();
  const router = useRouter();

  const shopSlug = params.shop;

  const [loading, setLoading] = useState(true);
  const [statusData, setStatusData] = useState(null);
  const [error, setError] = useState("");

  const loadStatus = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        "/api/ai-setup/provision/status",
        {
          method: "GET",
          headers: {
            Accept: "application/json",
          },
          cache: "no-store",
        }
      );

      if (response.status === 401) {
        router.push(
          `/login?next=/${shopSlug}/admin/ai-receptionist`
        );
        return;
      }

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data?.detail ||
            "Could not load your AI Receptionist."
        );
      }

      setStatusData(data);
    } catch (err) {
      setError(
        err.message ||
          "Could not load your AI Receptionist."
      );
    } finally {
      setLoading(false);
    }
  }, [router, shopSlug]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const provisioned = Boolean(
    statusData?.provisioned
  );

  const agentName =
    statusData?.agent_name ||
    `ChairTime AI - ${shopSlug}`;

  const phoneNumber =
    statusData?.phone_number ||
    statusData?.highlevel_phone_number ||
    "";

  return (
    <main className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-sky-50 px-6 py-10">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between gap-4 mb-6">
          <div>
            <p className="text-sm font-extrabold tracking-wider text-violet-600 uppercase mb-1">
              Admin
            </p>

            <h1 className="text-4xl sm:text-5xl font-extrabold text-slate-900">
              AI Receptionist
            </h1>

            <p className="text-gray-600 mt-2">
              Manage and test your AI phone receptionist.
            </p>
          </div>

          <button
            type="button"
            onClick={() =>
              router.push(`/${shopSlug}/admin`)
            }
            className="rounded-xl border border-slate-300 bg-white px-4 py-3 font-bold text-slate-700 hover:bg-slate-50"
          >
            ← Admin Home
          </button>
        </div>

        {loading ? (
          <div className="bg-white rounded-3xl shadow-lg border border-violet-100 p-7">
            <p className="font-bold text-slate-700">
              Loading your AI Receptionist...
            </p>
          </div>
        ) : error ? (
          <div className="bg-white rounded-3xl shadow-lg border border-red-200 p-7">
            <p className="font-extrabold text-red-700">
              Could not load AI Receptionist
            </p>

            <p className="text-red-600 mt-2">
              {error}
            </p>

            <button
              type="button"
              onClick={loadStatus}
              className="mt-5 rounded-xl bg-slate-900 px-5 py-3 font-bold text-white"
            >
              Try Again
            </button>
          </div>
        ) : (
          <div className="space-y-5">
            <section className="bg-white rounded-3xl shadow-lg border border-violet-100 p-7">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div className="flex items-center gap-4">
                  <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-fuchsia-500 to-violet-600 flex items-center justify-center text-2xl shadow-sm">
                    🤖
                  </div>

                  <div>
                    <h2 className="text-2xl font-extrabold text-slate-900">
                      {agentName}
                    </h2>

                    <p className="text-slate-600 mt-1">
                      Your dedicated AI phone receptionist
                    </p>
                  </div>
                </div>

                <span
                  className={
                    provisioned
                      ? "inline-flex rounded-full bg-emerald-100 px-4 py-2 text-sm font-extrabold text-emerald-700"
                      : "inline-flex rounded-full bg-amber-100 px-4 py-2 text-sm font-extrabold text-amber-700"
                  }
                >
                  {provisioned
                    ? "Active"
                    : "Setup Required"}
                </span>
              </div>

              {provisioned && (
                <div className="mt-6 rounded-2xl border border-emerald-200 bg-emerald-50 p-5">
                  <p className="font-extrabold text-emerald-800">
                    ✓ Your AI Receptionist is ready
                  </p>

                  <p className="text-sm text-emerald-700 mt-1">
                    It is connected to your ChairTime
                    services, staff, availability, and
                    booking system.
                  </p>
                </div>
              )}
            </section>

            <section className="bg-white rounded-3xl shadow-lg border border-sky-100 p-7">
              <h2 className="text-2xl font-extrabold text-slate-900">
                Phone Setup
              </h2>

              {phoneNumber ? (
                <>
                  <p className="text-slate-600 mt-2">
                    Your AI Receptionist phone number:
                  </p>

                  <p className="text-2xl font-extrabold text-slate-900 mt-3">
                    {phoneNumber}
                  </p>

                  <p className="text-sm text-slate-600 mt-4">
                    Forward your existing business phone
                    number to this number when you want
                    your AI Receptionist to answer calls.
                  </p>
                </>
              ) : (
                <>
                  <p className="text-slate-600 mt-2">
                    Your AI Receptionist has been created.
                    Phone routing has not been finalized
                    yet.
                  </p>

                  <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-5">
                    <p className="font-bold text-slate-800">
                      Phone number setup is the next step.
                    </p>

                    <p className="text-sm text-slate-600 mt-1">
                      We'll connect a dedicated phone number
                      and provide simple instructions for
                      forwarding your existing business
                      number to your AI Receptionist.
                    </p>
                  </div>
                </>
              )}
            </section>

            <section className="bg-white rounded-3xl shadow-lg border border-fuchsia-100 p-7">
              <h2 className="text-2xl font-extrabold text-slate-900">
                Test Your AI Receptionist
              </h2>

              <p className="text-slate-600 mt-2">
                Make sure your receptionist understands
                your services, staff, availability, and
                booking rules before you send customer
                calls to it.
              </p>

              {phoneNumber ? (
                <a
                  href={`tel:${phoneNumber}`}
                  className="inline-flex mt-5 rounded-xl bg-gradient-to-r from-fuchsia-600 to-violet-600 px-6 py-3 font-extrabold text-white shadow-md hover:shadow-lg"
                >
                  📞 Call My AI Receptionist
                </a>
              ) : (
                <button
                  type="button"
                  disabled
                  className="mt-5 rounded-xl bg-slate-200 px-6 py-3 font-extrabold text-slate-500 cursor-not-allowed"
                >
                  Test Call — Phone Setup Required
                </button>
              )}
            </section>

            <section className="bg-white rounded-3xl shadow-lg border border-slate-200 p-7">
              <h2 className="text-2xl font-extrabold text-slate-900">
                What Your Receptionist Can Do
              </h2>

              <div className="grid sm:grid-cols-2 gap-4 mt-5">
                <div className="rounded-2xl bg-slate-50 border border-slate-200 p-4">
                  <p className="font-extrabold">
                    📅 Check availability
                  </p>
                  <p className="text-sm text-slate-600 mt-1">
                    Uses your real ChairTime schedules.
                  </p>
                </div>

                <div className="rounded-2xl bg-slate-50 border border-slate-200 p-4">
                  <p className="font-extrabold">
                    ✂️ Explain services
                  </p>
                  <p className="text-sm text-slate-600 mt-1">
                    Uses the services configured for your
                    business.
                  </p>
                </div>

                <div className="rounded-2xl bg-slate-50 border border-slate-200 p-4">
                  <p className="font-extrabold">
                    👥 Work with staff
                  </p>
                  <p className="text-sm text-slate-600 mt-1">
                    Understands your staff and their
                    schedules.
                  </p>
                </div>

                <div className="rounded-2xl bg-slate-50 border border-slate-200 p-4">
                  <p className="font-extrabold">
                    ✓ Book appointments
                  </p>
                  <p className="text-sm text-slate-600 mt-1">
                    Creates appointments directly in
                    ChairTime.
                  </p>
                </div>
              </div>
            </section>
          </div>
        )}
      </div>
    </main>
  );
}
