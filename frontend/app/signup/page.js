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
      /*
       * Step 1:
       * Create the shop and owner account.
       *
       * The signup API also establishes the authenticated
       * ChairTime session needed for the Stripe Checkout
       * request that immediately follows.
       */
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
       * Step 2:
       * Immediately create Stripe Checkout.
       *
       * A new owner does NOT go to Admin or Setup here.
       * Stripe must first accept the payment method and
       * create the 30-day trial subscription.
       */
      const checkoutResponse = await fetch(
        "/api/billing/create-checkout-session",
        {
          method: "POST",
          headers: {
            Accept: "application/json",
          },
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

      /*
       * Step 3:
       * Leave ChairTime for Stripe-hosted Checkout.
       *
       * Stripe will return the owner to ChairTime only
       * after Checkout succeeds or is canceled.
       */
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
              Tell us a little about your business and
              create your ChairTime owner account.
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
              30 DAYS FREE — NO CHARGE TODAY
            </div>

            <div
              style={{
                fontWeight: "700",
                lineHeight: "1.55",
              }}
            >
              A credit card is required to start your
              free trial. You will not be charged today.
              Your first $49 payment will be charged
              after your 30-day trial unless you cancel.
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

            <div
              style={{
                background: "#eef2ff",
                border: "1px solid #c7d2fe",
                borderRadius: "14px",
                padding: "14px 16px",
                marginBottom: "16px",
                color: "#3730a3",
                fontSize: "14px",
                lineHeight: "1.5",
                fontWeight: "650",
              }}
            >
              <strong>Next: secure card setup.</strong>
              <br />
              After you create your account, you&apos;ll
              enter your card securely with Stripe.
              You&apos;ll pay $0 today and won&apos;t be
              charged until your 30-day free trial ends.
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
