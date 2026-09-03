"use client";

import Link from "next/link";
import { useState } from "react";
import styles from "./signup.module.css";

export default function SignupPage() {
  const [businessName, setBusinessName] = useState("");
  const [businessType, setBusinessType] =
    useState("service_business");
  const [phone, setPhone] = useState("");

  const [ownerName, setOwnerName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] =
    useState("");

  const [selectedPlan, setSelectedPlan] =
    useState("scheduling");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();

    if (loading) {
      return;
    }

    const cleanBusinessName = businessName.trim();
    const cleanOwnerName = ownerName.trim();
    const cleanEmail = email.trim().toLowerCase();
    const cleanPhone = phone.trim();

    if (!cleanBusinessName) {
      setError("Please enter your business name.");
      return;
    }

    if (!cleanOwnerName) {
      setError("Please enter your name.");
      return;
    }

    if (!cleanEmail) {
      setError("Please enter your email address.");
      return;
    }

    if (password.length < 8) {
      setError(
        "Your password must be at least 8 characters."
      );
      return;
    }

    if (password !== confirmPassword) {
      setError("The passwords do not match.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const signupResponse = await fetch(
        "/api/auth/signup",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify({
            business_name: cleanBusinessName,
            business_type: businessType,
            phone: cleanPhone || null,
            timezone:
              Intl.DateTimeFormat()
                .resolvedOptions()
                .timeZone ||
              "America/New_York",
            owner_name: cleanOwnerName,
            email: cleanEmail,
            password,
          }),
        }
      );

      let signupData = {};

      try {
        signupData =
          await signupResponse.json();
      } catch {
        signupData = {};
      }

      if (!signupResponse.ok) {
        throw new Error(
          signupData.detail ||
            signupData.error ||
            "Unable to create your account."
        );
      }

      const shopSlug =
        signupData?.shop?.slug ||
        signupData?.user?.shop_slug;

      if (!shopSlug) {
        throw new Error(
          "Your account was created, but ChairTime could not identify your business."
        );
      }

      /*
       * The owner does not enter Setup or Admin yet.
       * First, Stripe must accept a payment method
       * and create the 30-day trial subscription.
       */
      const checkoutResponse = await fetch(
        "/api/billing/create-checkout-session",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify({
            plan: selectedPlan,
          }),
        }
      );

      let checkoutData = {};

      try {
        checkoutData =
          await checkoutResponse.json();
      } catch {
        checkoutData = {};
      }

      if (!checkoutResponse.ok) {
        throw new Error(
          checkoutData.detail ||
            checkoutData.error ||
            "Your account was created, but we could not open the secure payment page. Please sign in and try again."
        );
      }

      const checkoutUrl =
        checkoutData.checkout_url ||
        checkoutData.url;

      if (!checkoutUrl) {
        throw new Error(
          "Your account was created, but Stripe did not return the secure payment page."
        );
      }

      window.location.href = checkoutUrl;
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to create your account. Please try again."
      );

      setLoading(false);
    }
  }

  const businessFeatures = [
    "Online booking 24/7",
    "Easy daily schedule and calendar",
    "Customer records and appointment history",
    "Text confirmations and reminders",
    "Staff schedules and availability",
    "Services, prices, and appointment times",
    "Customer notes",
    "Easy appointment changes and cancellations",
    "Card-on-file option to help reduce no-shows",
    "Access from your phone, tablet, or computer",
  ];

  const aiFeatures = [
    "Answers calls when you're busy with a customer",
    "Answers when your business is closed",
    "Books appointments directly into your schedule",
    "Handles routine scheduling questions",
    "Helps turn missed calls into booked appointments",
    "Lets you keep your existing business phone number",
    "Works with your online booking, schedule, and customer information",
  ];

  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <Link href="/" className={styles.backLink}>
          ← Back to ChairTime
        </Link>

        <section className={styles.card}>
          <div className={styles.brand}>
            <h1 className={styles.brandName}>
              Start your free month
            </h1>

            <p className={styles.brandText}>
              Tell us about your business, choose the
              plan that works best for you, and start
              your first 30 days free.
            </p>
          </div>

          <div
            className={styles.trial}
            style={{
              background:
                "linear-gradient(135deg, #fff7ed 0%, #fef3c7 100%)",
              border: "2px solid #f59e0b",
              borderRadius: "16px",
              padding: "18px 20px",
              color: "#78350f",
              boxShadow:
                "0 4px 14px rgba(245, 158, 11, 0.14)",
            }}
          >
            <div
              style={{
                fontSize: "17px",
                fontWeight: "900",
                color: "#b45309",
                marginBottom: "6px",
              }}
            >
              YOUR FIRST 30 DAYS ARE FREE — $0 TODAY
            </div>

            <div
              style={{
                fontWeight: "700",
                lineHeight: "1.55",
              }}
            >
              A credit card is required to start your
              free trial. You will not be charged
              today. Your selected plan begins billing
              after your 30-day trial unless you
              cancel.
            </div>
          </div>

          <form
            className={styles.form}
            onSubmit={handleSubmit}
          >
            {error ? (
              <p
                className={styles.error}
                role="alert"
              >
                {error}
              </p>
            ) : null}

            <section className={styles.section}>
              <h2 className={styles.sectionTitle}>
                Your business
              </h2>

              <div className={styles.grid}>
                <div className={styles.fullWidth}>
                  <div className={styles.field}>
                    <label
                      className={styles.label}
                      htmlFor="businessName"
                    >
                      Business Name
                    </label>

                    <p
                      style={{
                        margin: "-2px 0 7px",
                        color: "#64748b",
                        fontSize: "13px",
                        lineHeight: "1.4",
                      }}
                    >
                      Enter it exactly as you want
                      customers to see it.
                    </p>

                    <input
                      id="businessName"
                      className={styles.input}
                      type="text"
                      autoComplete="organization"
                      value={businessName}
                      onChange={(event) =>
                        setBusinessName(
                          event.target.value
                        )
                      }
                      placeholder="Mike's Barbershop"
                      disabled={loading}
                      required
                      autoFocus
                    />
                  </div>
                </div>

                <div className={styles.field}>
                  <label
                    className={styles.label}
                    htmlFor="businessType"
                  >
                    Business Type
                  </label>

                  <select
                    id="businessType"
                    className={styles.select}
                    value={businessType}
                    onChange={(event) =>
                      setBusinessType(
                        event.target.value
                      )
                    }
                    disabled={loading}
                  >
                    <option value="service_business">
                      Other Service Business
                    </option>

                    <option value="barbershop">
                      Barbershop
                    </option>

                    <option value="hair_salon">
                      Hair Salon
                    </option>

                    <option value="nail_salon">
                      Nail Salon
                    </option>

                    <option value="massage">
                      Massage / Wellness
                    </option>

                    <option value="trainer">
                      Personal Training / Fitness
                    </option>
                  </select>
                </div>

                <div className={styles.field}>
                  <label
                    className={styles.label}
                    htmlFor="phone"
                  >
                    Business Phone
                  </label>

                  <input
                    id="phone"
                    className={styles.input}
                    type="tel"
                    autoComplete="tel"
                    inputMode="tel"
                    value={phone}
                    onChange={(event) =>
                      setPhone(event.target.value)
                    }
                    placeholder="240-555-1234"
                    disabled={loading}
                  />
                </div>
              </div>
            </section>

            <section className={styles.section}>
              <h2 className={styles.sectionTitle}>
                Your account
              </h2>

              <div className={styles.grid}>
                <div className={styles.fullWidth}>
                  <div className={styles.field}>
                    <label
                      className={styles.label}
                      htmlFor="ownerName"
                    >
                      Your Name
                    </label>

                    <input
                      id="ownerName"
                      className={styles.input}
                      type="text"
                      autoComplete="name"
                      value={ownerName}
                      onChange={(event) =>
                        setOwnerName(
                          event.target.value
                        )
                      }
                      placeholder="Mike Smith"
                      disabled={loading}
                      required
                    />
                  </div>
                </div>

                <div className={styles.fullWidth}>
                  <div className={styles.field}>
                    <label
                      className={styles.label}
                      htmlFor="email"
                    >
                      Email
                    </label>

                    <input
                      id="email"
                      className={styles.input}
                      type="email"
                      autoComplete="email"
                      inputMode="email"
                      autoCapitalize="none"
                      spellCheck="false"
                      value={email}
                      onChange={(event) =>
                        setEmail(
                          event.target.value
                        )
                      }
                      placeholder="you@example.com"
                      disabled={loading}
                      required
                    />
                  </div>
                </div>

                <div className={styles.field}>
                  <label
                    className={styles.label}
                    htmlFor="password"
                  >
                    Password
                  </label>

                  <input
                    id="password"
                    className={styles.input}
                    type="password"
                    autoComplete="new-password"
                    value={password}
                    onChange={(event) =>
                      setPassword(
                        event.target.value
                      )
                    }
                    placeholder="At least 8 characters"
                    disabled={loading}
                    required
                  />
                </div>

                <div className={styles.field}>
                  <label
                    className={styles.label}
                    htmlFor="confirmPassword"
                  >
                    Confirm Password
                  </label>

                  <input
                    id="confirmPassword"
                    className={styles.input}
                    type="password"
                    autoComplete="new-password"
                    value={confirmPassword}
                    onChange={(event) =>
                      setConfirmPassword(
                        event.target.value
                      )
                    }
                    placeholder="Enter password again"
                    disabled={loading}
                    required
                  />
                </div>
              </div>
            </section>

            <section className={styles.section}>
              <div
                style={{
                  marginBottom: "18px",
                }}
              >
                <h2 className={styles.sectionTitle}>
                  Choose your plan
                </h2>

                <p
                  style={{
                    color: "#64748b",
                    fontSize: "14px",
                    lineHeight: "1.55",
                    marginTop: "5px",
                  }}
                >
                  Both plans include your first 30 days
                  free. Choose what works best for your
                  business.
                </p>
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns:
                    "repeat(auto-fit, minmax(260px, 1fr))",
                  gap: "16px",
                }}
              >
                <button
                  type="button"
                  onClick={() =>
                    setSelectedPlan("scheduling")
                  }
                  disabled={loading}
                  style={{
                    textAlign: "left",
                    padding: "20px",
                    borderRadius: "18px",
                    border:
                      selectedPlan === "scheduling"
                        ? "3px solid #4f46e5"
                        : "2px solid #cbd5e1",
                    background:
                      selectedPlan === "scheduling"
                        ? "#eef2ff"
                        : "#ffffff",
                    cursor: loading
                      ? "default"
                      : "pointer",
                    boxShadow:
                      selectedPlan === "scheduling"
                        ? "0 5px 18px rgba(79,70,229,0.12)"
                        : "none",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent:
                        "space-between",
                      alignItems: "flex-start",
                      gap: "12px",
                    }}
                  >
                    <div>
                      <div
                        style={{
                          fontSize: "21px",
                          fontWeight: "900",
                          color: "#0f172a",
                        }}
                      >
                        Business Management
                      </div>

                      <div
                        style={{
                          marginTop: "4px",
                          fontSize: "20px",
                          fontWeight: "900",
                          color: "#4f46e5",
                        }}
                      >
                        $49/month
                      </div>
                    </div>

                    <div
                      style={{
                        width: "22px",
                        height: "22px",
                        borderRadius: "50%",
                        border:
                          selectedPlan ===
                          "scheduling"
                            ? "6px solid #4f46e5"
                            : "2px solid #94a3b8",
                        background: "#ffffff",
                        flexShrink: 0,
                      }}
                    />
                  </div>

                  <p
                    style={{
                      marginTop: "14px",
                      marginBottom: "14px",
                      color: "#475569",
                      fontWeight: "700",
                      lineHeight: "1.5",
                    }}
                  >
                    Everything you need to manage
                    appointments and customers simply.
                  </p>

                  <div
                    style={{
                      display: "grid",
                      gap: "8px",
                    }}
                  >
                    {businessFeatures.map(
                      (feature) => (
                        <div
                          key={feature}
                          style={{
                            display: "flex",
                            gap: "8px",
                            color: "#334155",
                            fontSize: "14px",
                            lineHeight: "1.4",
                          }}
                        >
                          <span
                            style={{
                              color: "#16a34a",
                              fontWeight: "900",
                            }}
                          >
                            ✓
                          </span>

                          <span>{feature}</span>
                        </div>
                      )
                    )}
                  </div>

                  <div
                    style={{
                      marginTop: "18px",
                      padding: "10px 12px",
                      borderRadius: "10px",
                      background: "#ffffff",
                      color: "#3730a3",
                      fontWeight: "800",
                      fontSize: "13px",
                    }}
                  >
                    Your first 30 days are free.
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() =>
                    setSelectedPlan(
                      "scheduling_ai"
                    )
                  }
                  disabled={loading}
                  style={{
                    textAlign: "left",
                    padding: "20px",
                    borderRadius: "18px",
                    border:
                      selectedPlan ===
                      "scheduling_ai"
                        ? "3px solid #7c3aed"
                        : "2px solid #c4b5fd",
                    background:
                      selectedPlan ===
                      "scheduling_ai"
                        ? "#f5f3ff"
                        : "#fafaff",
                    cursor: loading
                      ? "default"
                      : "pointer",
                    boxShadow:
                      selectedPlan ===
                      "scheduling_ai"
                        ? "0 5px 18px rgba(124,58,237,0.14)"
                        : "none",
                    position: "relative",
                  }}
                >
                  <div
                    style={{
                      display: "inline-block",
                      marginBottom: "12px",
                      padding: "6px 10px",
                      borderRadius: "999px",
                      background: "#7c3aed",
                      color: "#ffffff",
                      fontSize: "12px",
                      fontWeight: "900",
                    }}
                  >
                    BEST FOR BUSY BUSINESSES
                  </div>

                  <div
                    style={{
                      display: "flex",
                      justifyContent:
                        "space-between",
                      alignItems: "flex-start",
                      gap: "12px",
                    }}
                  >
                    <div>
                      <div
                        style={{
                          fontSize: "21px",
                          fontWeight: "900",
                          color: "#0f172a",
                        }}
                      >
                        Business Management
                        <br />
                        + AI Receptionist
                      </div>

                      <div
                        style={{
                          marginTop: "4px",
                          fontSize: "20px",
                          fontWeight: "900",
                          color: "#7c3aed",
                        }}
                      >
                        $198/month
                      </div>
                    </div>

                    <div
                      style={{
                        width: "22px",
                        height: "22px",
                        borderRadius: "50%",
                        border:
                          selectedPlan ===
                          "scheduling_ai"
                            ? "6px solid #7c3aed"
                            : "2px solid #94a3b8",
                        background: "#ffffff",
                        flexShrink: 0,
                      }}
                    />
                  </div>

                  <div
                    style={{
                      marginTop: "14px",
                      marginBottom: "15px",
                      padding: "12px",
                      borderRadius: "12px",
                      background: "#ede9fe",
                      color: "#5b21b6",
                      fontWeight: "900",
                      lineHeight: "1.45",
                    }}
                  >
                    Never lose a customer because you
                    couldn&apos;t answer the phone.
                  </div>

                  <p
                    style={{
                      color: "#475569",
                      fontWeight: "700",
                      lineHeight: "1.5",
                      marginBottom: "13px",
                    }}
                  >
                    Everything in Business Management,
                    plus an AI receptionist that answers
                    the phone for you.
                  </p>

                  <div
                    style={{
                      display: "grid",
                      gap: "8px",
                    }}
                  >
                    {aiFeatures.map((feature) => (
                      <div
                        key={feature}
                        style={{
                          display: "flex",
                          gap: "8px",
                          color: "#334155",
                          fontSize: "14px",
                          lineHeight: "1.4",
                        }}
                      >
                        <span
                          style={{
                            color: "#7c3aed",
                            fontWeight: "900",
                          }}
                        >
                          ✓
                        </span>

                        <span>{feature}</span>
                      </div>
                    ))}
                  </div>

                  <div
                    style={{
                      marginTop: "18px",
                      padding: "10px 12px",
                      borderRadius: "10px",
                      background: "#ffffff",
                      color: "#5b21b6",
                      fontWeight: "800",
                      fontSize: "13px",
                    }}
                  >
                    Your first 30 days are free.
                  </div>
                </button>
              </div>
            </section>

            <div
              style={{
                background: "#eef2ff",
                border: "1px solid #c7d2fe",
                borderRadius: "14px",
                padding: "16px",
                marginBottom: "16px",
                color: "#3730a3",
                fontSize: "14px",
                lineHeight: "1.55",
                fontWeight: "650",
              }}
            >
              <strong>
                Next: secure card setup with Stripe.
              </strong>
              <br />
              A credit card is required to start your
              free trial, but you&apos;ll pay{" "}
              <strong>$0 today</strong>. You won&apos;t
              be charged until your 30-day free trial
              ends.
              <br />
              <br />
              After 30 days, your selected plan will be{" "}
              <strong>
                {selectedPlan === "scheduling_ai"
                  ? "$198 per month"
                  : "$49 per month"}
              </strong>{" "}
              unless you cancel.
            </div>

            <button
              className={styles.button}
              type="submit"
              disabled={loading}
            >
              {loading
                ? "Opening Secure Checkout..."
                : "Create Account & Start Free Trial"}
            </button>
          </form>

          <p className={styles.footer}>
            Already have a ChairTime account?{" "}
            <Link
              href="/login"
              className={styles.loginLink}
            >
              Sign in
            </Link>
          </p>
        </section>
      </div>
    </main>
  );
}
