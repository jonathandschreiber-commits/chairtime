"use client";

import Link from "next/link";
import { useState } from "react";
import styles from "./login.module.css";

export default function PasswordRecoveryForm({ reset = false }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [complete, setComplete] = useState(false);

  async function submit(event) {
    event.preventDefault();
    if (loading) return;

    const fields = new FormData(event.currentTarget);
    const password = fields.get("password");
    const token = reset ? new URLSearchParams(window.location.hash.slice(1)).get("token") : null;

    if (reset && !token) {
      setError("Open the link in your reset email or request a new link.");
      return;
    }
    if (reset && password !== fields.get("confirm")) {
      setError("The passwords do not match.");
      return;
    }

    setError("");
    setLoading(true);
    try {
      const action = reset ? "reset-password" : "forgot-password";
      const response = await fetch(`/api/auth/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(reset ? { token, password } : { email: fields.get("email").trim() }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Unable to complete your request. Please try again.");
      }
      if (reset) window.history.replaceState(null, "", window.location.pathname);
      setComplete(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className={styles.page}>
      <section className={styles.card}>
        <div className={styles.brand}>
          <h1 className={styles.brandName}>{reset ? "Set a new password" : "Forgot your password?"}</h1>
          <p className={styles.brandText} role={complete ? "status" : undefined}>
            {complete
              ? reset
                ? "Your password has been changed. Sign in with your new password."
                : "If an active account uses that email, a reset link will arrive shortly. Check your spam folder if needed."
              : reset
                ? "Choose a new password for your DayTello account."
                : "Enter the email address you use to sign in to DayTello."}
          </p>
        </div>

        {!complete && (
          <form className={styles.form} onSubmit={submit}>
            {error && <p className={styles.error} role="alert">{error}</p>}
            {reset ? (
              <>
                <div className={styles.field}>
                  <label className={styles.label} htmlFor="new-password">New password</label>
                  <input className={styles.input} id="new-password" name="password" type="password"
                    autoComplete="new-password" minLength={8} maxLength={72} disabled={loading}
                    aria-describedby="password-hint" required />
                  <p id="password-hint" className="text-sm text-gray-600">Use at least 8 characters.</p>
                </div>
                <div className={styles.field}>
                  <label className={styles.label} htmlFor="confirm-password">Confirm password</label>
                  <input className={styles.input} id="confirm-password" name="confirm" type="password"
                    autoComplete="new-password" maxLength={72} disabled={loading} required />
                </div>
              </>
            ) : (
              <div className={styles.field}>
                <label className={styles.label} htmlFor="reset-email">Email</label>
                <input className={styles.input} id="reset-email" name="email" type="email"
                  autoComplete="email" maxLength={254} disabled={loading} required />
              </div>
            )}
            <button className={styles.button} disabled={loading}>
              {loading ? "Please wait…" : reset ? "Save new password" : "Email me a reset link"}
            </button>
          </form>
        )}

        {reset && !complete && (
          <p className={styles.footer}>
            <Link className={styles.recoveryLink} href="/login/forgot-password">Request a new link</Link>
          </p>
        )}
        <p className={styles.footer}>
          <Link className={styles.recoveryLink} href="/login">Back to sign in</Link>
        </p>
      </section>
    </main>
  );
}
