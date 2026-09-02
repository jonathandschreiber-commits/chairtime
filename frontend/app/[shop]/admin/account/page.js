"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

export default function AccountOptionsPage() {
  const params = useParams();
  const shop = params?.shop || "";

  const [account, setAccount] = useState(null);
  const [invoices, setInvoices] = useState([]);

  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const [savingPolicy, setSavingPolicy] = useState(false);
  const [openingBilling, setOpeningBilling] = useState(false);
  const [openingStripe, setOpeningStripe] = useState(false);
  const [startingTrial, setStartingTrial] = useState(false);
  const [changingSubscription, setChangingSubscription] =
    useState(false);

  useEffect(() => {
    loadAccount();
  }, []);

  async function loadAccount() {
    setLoading(true);
    setError("");

    try {
      const [summaryResponse, invoicesResponse] =
        await Promise.all([
          fetch("/api/account/summary", {
            cache: "no-store",
          }),
          fetch("/api/account/invoices", {
            cache: "no-store",
          }),
        ]);

      if (!summaryResponse.ok) {
        const data = await summaryResponse
          .json()
          .catch(() => ({}));

        throw new Error(
          data?.detail ||
            "Unable to load account information."
        );
      }

      const summaryData =
        await summaryResponse.json();

      setAccount(summaryData);

      if (invoicesResponse.ok) {
        const invoiceData =
          await invoicesResponse.json();

        setInvoices(
          Array.isArray(invoiceData?.invoices)
            ? invoiceData.invoices
            : []
        );
      } else {
        setInvoices([]);
      }
    } catch (err) {
      setError(
        err?.message ||
          "Unable to load account information."
      );
    } finally {
      setLoading(false);
    }
  }

  function formatDate(value) {
    if (!value) {
      return "";
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return "";
    }

    return date.toLocaleDateString(
      undefined,
      {
        year: "numeric",
        month: "long",
        day: "numeric",
      }
    );
  }

  function formatMoney(cents, currency = "usd") {
    const amount =
      Number(cents || 0) / 100;

    try {
      return new Intl.NumberFormat(
        undefined,
        {
          style: "currency",
          currency:
            String(currency || "usd")
              .toUpperCase(),
        }
      ).format(amount);
    } catch {
      return `$${amount.toFixed(2)}`;
    }
  }

  function friendlySubscriptionStatus(value) {
    const status =
      String(value || "").toLowerCase();

    if (status === "trialing") {
      return "Free Trial";
    }

    if (status === "active") {
      return "Active";
    }

    if (status === "past_due") {
      return "Payment Due";
    }

    if (status === "canceled") {
      return "Canceled";
    }

    if (status === "unpaid") {
      return "Unpaid";
    }

    if (!status) {
      return "Not Started";
    }

    return status
      .replaceAll("_", " ")
      .replace(/\b\w/g, (letter) =>
        letter.toUpperCase()
      );
  }

  async function startFreeTrial() {
    setStartingTrial(true);
    setError("");
    setMessage("");

    try {
      const response = await fetch(
        "/api/billing/create-checkout-session",
        {
          method: "POST",
        }
      );

      const data = await response
        .json()
        .catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data?.detail ||
            "Unable to start your free trial."
        );
      }

      if (!data?.checkout_url) {
        throw new Error(
          "Stripe checkout link was not returned."
        );
      }

      window.location.href =
        data.checkout_url;
    } catch (err) {
      setError(
        err?.message ||
          "Unable to start your free trial."
      );

      setStartingTrial(false);
    }
  }

  async function openBillingPortal() {
    setOpeningBilling(true);
    setError("");
    setMessage("");

    try {
      const response = await fetch(
        "/api/account/billing-portal",
        {
          method: "POST",
        }
      );

      const data = await response
        .json()
        .catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data?.detail ||
            "Unable to open billing."
        );
      }

      if (!data?.portal_url) {
        throw new Error(
          "Billing link was not returned."
        );
      }

      window.location.href =
        data.portal_url;
    } catch (err) {
      setError(
        err?.message ||
          "Unable to open billing."
      );

      setOpeningBilling(false);
    }
  }

  async function updatePaymentPolicy(
    paymentPolicy
  ) {
    setSavingPolicy(true);
    setError("");
    setMessage("");

    try {
      const response = await fetch(
        "/api/account/payment-policy",
        {
          method: "PATCH",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            payment_policy:
              paymentPolicy,
          }),
        }
      );

      const data = await response
        .json()
        .catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data?.detail ||
            "Unable to save payment settings."
        );
      }

      setAccount((current) => ({
        ...current,
        customer_payments: {
          ...current.customer_payments,
          payment_policy:
            data.payment_policy,
        },
      }));

      setMessage(
        "Customer payment settings saved."
      );
    } catch (err) {
      setError(
        err?.message ||
          "Unable to save payment settings."
      );
    } finally {
      setSavingPolicy(false);
    }
  }

  async function openStripeDashboard() {
    setOpeningStripe(true);
    setError("");
    setMessage("");

    try {
      const response = await fetch(
        "/api/account/stripe-dashboard",
        {
          method: "POST",
        }
      );

      const data = await response
        .json()
        .catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data?.detail ||
            "Unable to open payment dashboard."
        );
      }

      if (!data?.dashboard_url) {
        throw new Error(
          "Payment dashboard link was not returned."
        );
      }

      window.location.href =
        data.dashboard_url;
    } catch (err) {
      setError(
        err?.message ||
          "Unable to open payment dashboard."
      );

      setOpeningStripe(false);
    }
  }

  async function cancelSubscription() {
    const confirmed = window.confirm(
      "Cancel your ChairTime subscription at the end of the current billing period? You can continue using ChairTime until then."
    );

    if (!confirmed) {
      return;
    }

    setChangingSubscription(true);
    setError("");
    setMessage("");

    try {
      const response = await fetch(
        "/api/account/cancel-subscription",
        {
          method: "POST",
        }
      );

      const data = await response
        .json()
        .catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data?.detail ||
            "Unable to cancel subscription."
        );
      }

      setMessage(
        data?.message ||
          "Your subscription is scheduled to cancel."
      );

      await loadAccount();
    } catch (err) {
      setError(
        err?.message ||
          "Unable to cancel subscription."
      );
    } finally {
      setChangingSubscription(false);
    }
  }

  async function reactivateSubscription() {
    setChangingSubscription(true);
    setError("");
    setMessage("");

    try {
      const response = await fetch(
        "/api/account/reactivate-subscription",
        {
          method: "POST",
        }
      );

      const data = await response
        .json()
        .catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data?.detail ||
            "Unable to keep subscription active."
        );
      }

      setMessage(
        data?.message ||
          "Your subscription will continue normally."
      );

      await loadAccount();
    } catch (err) {
      setError(
        err?.message ||
          "Unable to keep subscription active."
      );
    } finally {
      setChangingSubscription(false);
    }
  }

  if (loading) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-sky-50 px-5 py-10">
        <div className="max-w-4xl mx-auto">
          <div className="bg-white rounded-3xl border border-slate-200 shadow-sm p-8 text-center">
            <p className="text-slate-600 font-semibold">
              Loading account options...
            </p>
          </div>
        </div>
      </main>
    );
  }

  const subscription =
    account?.subscription || {};

  const payments =
    account?.customer_payments || {};

  const paymentPolicy =
    payments.payment_policy || "none";

  const hasSubscription =
    Boolean(subscription.has_subscription);

  const subscriptionStatus =
    friendlySubscriptionStatus(
      subscription.status
    );

  const statusIsGood =
    subscription.status === "active" ||
    subscription.status === "trialing";

  const trialDate =
    formatDate(
      subscription.trial_ends_at
    );

  const periodEndDate =
    formatDate(
      subscription.current_period_ends_at
    );

  return (
    <main className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-sky-50 px-5 py-8 sm:py-10">
      <div className="max-w-4xl mx-auto">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-7">
          <div>
            <p className="text-sm font-extrabold tracking-wider text-indigo-600 uppercase">
              Admin
            </p>

            <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 mt-1">
              Account Options
            </h1>

            <p className="text-slate-600 mt-2">
              Manage your subscription and payment settings.
            </p>
          </div>

          <a
            href={`/${shop}/admin`}
            className="inline-flex items-center justify-center rounded-xl border border-slate-300 bg-white px-4 py-2.5 font-bold text-slate-700 hover:bg-slate-50"
          >
            ← Admin Home
          </a>
        </div>

        {error ? (
          <div className="mb-5 rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-red-700 font-semibold">
            {error}
          </div>
        ) : null}

        {message ? (
          <div className="mb-5 rounded-2xl border border-emerald-200 bg-emerald-50 px-5 py-4 text-emerald-700 font-semibold">
            {message}
          </div>
        ) : null}

        <section className="bg-white rounded-3xl border border-indigo-100 shadow-sm p-6 sm:p-7 mb-5">
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-2xl bg-indigo-100 flex items-center justify-center text-2xl">
                  💳
                </div>

                <div>
                  <h2 className="text-2xl font-extrabold text-slate-900">
                    Subscription
                  </h2>

                  <p className="text-slate-500 text-sm">
                    Your ChairTime account
                  </p>
                </div>
              </div>

              <div className="mt-6">
                <p className="text-xl font-extrabold text-slate-900">
                  ChairTime Scheduling
                </p>

                <p className="text-slate-600 mt-1">
                  $49 per month
                </p>
              </div>
            </div>

            <span
              className={`inline-flex self-start rounded-full px-4 py-2 text-sm font-extrabold ${
                statusIsGood
                  ? "bg-emerald-100 text-emerald-700"
                  : "bg-amber-100 text-amber-700"
              }`}
            >
              {subscriptionStatus}
            </span>
          </div>

          {!hasSubscription ? (
            <div className="mt-6 rounded-2xl border-2 border-indigo-200 bg-indigo-50 p-5">
              <p className="text-lg font-extrabold text-slate-900">
                Start your 30-day free trial
              </p>

              <p className="text-slate-700 mt-2">
                Try ChairTime free for 30 days.
                There is no charge today.
                After your trial, your
                subscription is $49 per month
                unless you cancel.
              </p>
            </div>
          ) : (
            <div className="mt-6 rounded-2xl bg-slate-50 border border-slate-200 p-5">
              {subscription.status ===
                "trialing" &&
              trialDate ? (
                <p className="text-slate-700">
                  Your free trial ends{" "}
                  <strong>{trialDate}</strong>.
                  Your $49 monthly subscription
                  begins after the trial unless
                  you cancel.
                </p>
              ) : subscription.cancel_at_period_end ? (
                <p className="text-slate-700">
                  Your subscription is scheduled
                  to end
                  {periodEndDate ? (
                    <>
                      {" "}
                      on{" "}
                      <strong>
                        {periodEndDate}
                      </strong>
                    </>
                  ) : null}
                  .
                </p>
              ) : periodEndDate ? (
                <p className="text-slate-700">
                  Your next billing period begins{" "}
                  <strong>
                    {periodEndDate}
                  </strong>
                  .
                </p>
              ) : (
                <p className="text-slate-700">
                  Manage your ChairTime
                  subscription and billing
                  information here.
                </p>
              )}
            </div>
          )}

          <div className="mt-5 flex flex-col sm:flex-row gap-3">
            {!hasSubscription ? (
              <button
                type="button"
                onClick={startFreeTrial}
                disabled={startingTrial}
                className="rounded-xl bg-indigo-600 px-5 py-3 font-extrabold text-white hover:bg-indigo-700 disabled:opacity-60"
              >
                {startingTrial
                  ? "Opening Secure Checkout..."
                  : "Start My Free Trial"}
              </button>
            ) : (
              <>
                <button
                  type="button"
                  onClick={openBillingPortal}
                  disabled={openingBilling}
                  className="rounded-xl bg-indigo-600 px-5 py-3 font-extrabold text-white hover:bg-indigo-700 disabled:opacity-60"
                >
                  {openingBilling
                    ? "Opening..."
                    : "Manage Billing"}
                </button>

                {subscription.cancel_at_period_end ? (
                  <button
                    type="button"
                    onClick={
                      reactivateSubscription
                    }
                    disabled={
                      changingSubscription
                    }
                    className="rounded-xl border border-emerald-300 bg-emerald-50 px-5 py-3 font-extrabold text-emerald-700 hover:bg-emerald-100 disabled:opacity-60"
                  >
                    {changingSubscription
                      ? "Saving..."
                      : "Keep My Subscription"}
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={
                      cancelSubscription
                    }
                    disabled={
                      changingSubscription
                    }
                    className="rounded-xl border border-slate-300 bg-white px-5 py-3 font-bold text-slate-600 hover:bg-slate-50 disabled:opacity-60"
                  >
                    {changingSubscription
                      ? "Saving..."
                      : "Cancel Subscription"}
                  </button>
                )}
              </>
            )}
          </div>
        </section>

        <section className="bg-white rounded-3xl border border-emerald-100 shadow-sm p-6 sm:p-7 mb-5">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-12 h-12 rounded-2xl bg-emerald-100 flex items-center justify-center text-2xl">
              💵
            </div>

            <div>
              <h2 className="text-2xl font-extrabold text-slate-900">
                Customer Payments
              </h2>

              <p className="text-slate-500 text-sm">
                Choose how customers use cards
                with your business.
              </p>
            </div>
          </div>

          <div className="space-y-3">
            {[
              {
                value: "none",
                title:
                  "Don't accept cards",
                description:
                  "Customers book without entering a card.",
              },
              {
                value: "accept_cards",
                title:
                  "Accept card payments",
                description:
                  "Use Stripe to accept customer card payments.",
              },
              {
                value: "card_required",
                title:
                  "Require a card to reserve",
                description:
                  "Customers save a card when making a reservation.",
              },
            ].map((option) => {
              const selected =
                paymentPolicy ===
                option.value;

              return (
                <button
                  key={option.value}
                  type="button"
                  disabled={savingPolicy}
                  onClick={() =>
                    updatePaymentPolicy(
                      option.value
                    )
                  }
                  className={`w-full text-left rounded-2xl border-2 p-4 transition ${
                    selected
                      ? "border-emerald-500 bg-emerald-50"
                      : "border-slate-200 bg-white hover:border-slate-300"
                  } disabled:opacity-60`}
                >
                  <div className="flex gap-3">
                    <div
                      className={`mt-0.5 w-5 h-5 shrink-0 rounded-full border-2 flex items-center justify-center ${
                        selected
                          ? "border-emerald-600"
                          : "border-slate-300"
                      }`}
                    >
                      {selected ? (
                        <div className="w-2.5 h-2.5 rounded-full bg-emerald-600" />
                      ) : null}
                    </div>

                    <div>
                      <p className="font-extrabold text-slate-900">
                        {option.title}
                      </p>

                      <p className="text-sm text-slate-600 mt-1">
                        {option.description}
                      </p>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>

          <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-5">
            {payments.charges_enabled &&
            payments.payouts_enabled ? (
              <>
                <p className="font-extrabold text-emerald-700">
                  ✓ Payment account connected
                </p>

                <p className="text-sm text-slate-600 mt-1">
                  Your Stripe account is ready
                  to accept customer payments
                  and receive payouts.
                </p>

                <button
                  type="button"
                  onClick={
                    openStripeDashboard
                  }
                  disabled={openingStripe}
                  className="mt-4 rounded-xl border border-slate-300 bg-white px-4 py-2.5 font-bold text-slate-700 hover:bg-slate-100 disabled:opacity-60"
                >
                  {openingStripe
                    ? "Opening..."
                    : "Open Payment Dashboard"}
                </button>
              </>
            ) : payments.connected_account_exists ? (
              <>
                <p className="font-extrabold text-amber-700">
                  Payment setup needs attention
                </p>

                <p className="text-sm text-slate-600 mt-1">
                  Finish your Stripe setup
                  before accepting customer
                  cards.
                </p>
              </>
            ) : (
              <>
                <p className="font-extrabold text-slate-800">
                  Card payments are not set up
                </p>

                <p className="text-sm text-slate-600 mt-1">
                  You can connect Stripe if
                  you decide to accept or
                  require customer cards.
                </p>
              </>
            )}
          </div>
        </section>

        <section className="bg-white rounded-3xl border border-sky-100 shadow-sm p-6 sm:p-7">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-12 h-12 rounded-2xl bg-sky-100 flex items-center justify-center text-2xl">
              🧾
            </div>

            <div>
              <h2 className="text-2xl font-extrabold text-slate-900">
                Payment History
              </h2>

              <p className="text-slate-500 text-sm">
                Payments for your ChairTime
                subscription.
              </p>
            </div>
          </div>

          {invoices.length === 0 ? (
            <div className="rounded-2xl bg-slate-50 border border-slate-200 p-5">
              <p className="font-bold text-slate-800">
                No subscription payments yet.
              </p>

              <p className="text-sm text-slate-600 mt-1">
                {hasSubscription
                  ? "If you're still in your free trial, your first payment will appear here after the trial ends."
                  : "Your subscription payment history will appear here after you start your free trial."}
              </p>
            </div>
          ) : (
            <div className="divide-y divide-slate-200 border border-slate-200 rounded-2xl overflow-hidden">
              {invoices.map(
                (invoice) => (
                  <div
                    key={invoice.id}
                    className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3"
                  >
                    <div>
                      <p className="font-extrabold text-slate-900">
                        {formatMoney(
                          invoice.amount_paid ||
                            invoice.amount_due,
                          invoice.currency
                        )}
                      </p>

                      <p className="text-sm text-slate-500 mt-1">
                        {formatDate(
                          invoice.created_at
                        )}
                      </p>
                    </div>

                    <div className="flex items-center gap-3">
                      <span
                        className={`rounded-full px-3 py-1.5 text-xs font-extrabold ${
                          invoice.paid
                            ? "bg-emerald-100 text-emerald-700"
                            : "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {invoice.paid
                          ? "Paid"
                          : invoice.status ||
                            "Pending"}
                      </span>

                      {invoice.hosted_invoice_url ? (
                        <a
                          href={
                            invoice.hosted_invoice_url
                          }
                          target="_blank"
                          rel="noreferrer"
                          className="font-bold text-indigo-600 hover:text-indigo-800"
                        >
                          View Invoice
                        </a>
                      ) : null}
                    </div>
                  </div>
                )
              )}
            </div>
          )}
        </section>

        <p className="text-center text-sm text-slate-500 mt-8">
          ChairTime keeps your subscription
          billing and customer payments
          separate so they're easy to manage.
        </p>
      </div>
    </main>
  );
}
