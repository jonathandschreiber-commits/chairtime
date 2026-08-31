"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import styles from "./signup.module.css";

export default function SignupPage() {
  const router = useRouter();

  const [businessName, setBusinessName] = useState("");
  const [businessType, setBusinessType] = useState("service_business");
  const [phone, setPhone] = useState("");

  const [ownerName, setOwnerName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

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
      setError("Your password must be at least 8 characters.");
      return;
    }

    if (password !== confirmPassword) {
      setError("The passwords do not match.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await fetch("/api/auth/signup", {
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
            Intl.DateTimeFormat().resolvedOptions().timeZone ||
            "America/New_York",
          owner_name: cleanOwnerName,
          email: cleanEmail,
          password,
        }),
      });

      let data = {};

      try {
        data = await response.json();
      } catch {
        data = {};
      }

      if (!response.ok) {
        throw new Error(
          data.detail ||
            data.error ||
            "Unable to create your account."
        );
      }

      const shopSlug =
        data?.shop?.slug ||
        data?.user?.shop_slug;

      if (!shopSlug) {
        throw new Error(
          "Your account was created, but ChairTime could not identify your business."
        );
      }

      /*
       * TEMPORARY:
       * Until Stripe onboarding is added, send the new owner
       * to the shop's Admin Home so we can verify signup
       * end-to-end.
       *
       * The next development step will replace this destination
       * with the payment/free-trial screen.
       */
      router.replace(`/${shopSlug}/admin`);
      router.refresh();
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to create your account. Please try again."
      );
    } finally {
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
              Tell us a little about your business and create
              your ChairTime owner account.
            </p>
          </div>

          <div className={styles.trial}>
            Free for 30 days. No charge today.
            <br />
            We&apos;ll ask for payment information before your
            trial begins.
          </div>

          <form className={styles.form} onSubmit={handleSubmit}>
            {error ? (
              <p className={styles.error} role="alert">
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
                      Enter it exactly as you want customers to see it.
                    </p>

                    <input
                      id="businessName"
                      className={styles.input}
                      type="text"
                      autoComplete="organization"
                      value={businessName}
                      onChange={(event) =>
                        setBusinessName(event.target.value)
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
                      setBusinessType(event.target.value)
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
                        setOwnerName(event.target.value)
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
                        setEmail(event.target.value)
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
                      setPassword(event.target.value)
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
                      setConfirmPassword(event.target.value)
                    }
                    placeholder="Enter password again"
                    disabled={loading}
                    required
                  />
                </div>
              </div>
            </section>

            <button
              className={styles.button}
              type="submit"
              disabled={loading}
            >
              {loading
                ? "Creating Your Account..."
                : "Continue"}
            </button>
          </form>

          <p className={styles.footer}>
            Already have a ChairTime account?{" "}
            <Link href="/login" className={styles.loginLink}>
              Sign in
            </Link>
          </p>
        </section>
      </div>
    </main>
  );
}
