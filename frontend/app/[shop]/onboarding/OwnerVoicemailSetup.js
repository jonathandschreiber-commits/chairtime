"use client";

import { useEffect, useState } from "react";
import styles from "./onboarding.module.css";

export default function OwnerVoicemailSetup({ shopSlug, onReadyChange }) {
  const url = `/api/shops/${encodeURIComponent(shopSlug)}/owner-voicemail`;
  const [available, setAvailable] = useState(false);
  const [number, setNumber] = useState("");
  const [consent, setConsent] = useState(false);
  const [code, setCode] = useState("");
  const [phase, setPhase] = useState("start");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    fetch(url, { cache: "no-store" })
      .then(async (response) => response.ok ? response.json() : null)
      .then((data) => {
        if (!active || !data) return;
        setAvailable(true);
        if (data.configuration_complete) {
          setPhase("done");
          onReadyChange(true);
        }
      })
      .catch(() => {});
    return () => { active = false; };
  }, [url, onReadyChange]);

  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    const digits = number.replace(/\D/g, "");
    const local = digits.length === 11 && digits.startsWith("1") ? digits.slice(1) : digits;
    if (!/^[2-9]\d{2}[2-9]\d{6}$/.test(local)) {
      setError("Enter a valid 10-digit phone number.");
      return;
    }
    setError("");
    setBusy(true);
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: phase, phone_number: "+1" + local, consent, code }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Could not complete voicemail setup.");
      if (phase === "start" && data.verification_sent) setPhase("confirm");
      else if (phase === "confirm" && data.owner_number_verified) setPhase("save");
      else if (phase === "save" && data.configuration_complete) {
        setPhase("done");
        onReadyChange(true);
      } else throw new Error(data.message || "Voicemail setup could not be confirmed.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (!available) return null;

  return (
    <section style={{ marginTop: 16, padding: 16, border: "1px solid #c4b5fd", borderRadius: 12 }}>
      <h3 style={{ fontWeight: 800 }}>Forward calls and get voicemail texts</h3>
      {phase === "done" ? (
        <p role="status">Setup saved. Call your AI number, ask for an employee, and leave a voicemail if the call goes unanswered. Check your texts for the recording link.</p>
      ) : (
        <form onSubmit={submit} style={{ display: "grid", gap: 16, marginTop: 12 }}>
          <p>Use a number you control. DayTello will try this number when callers ask for an employee and text a recording link if they leave a voicemail.</p>
          <div>
            <label className={styles.formLabel} htmlFor="daytello-owner-phone">Owner phone number</label>
            <input id="daytello-owner-phone" className={styles.textInput} type="tel"
              autoComplete="tel" placeholder="(555) 123-4567"
              style={{ borderColor: "#3b82f6", backgroundColor: "#eff6ff" }}
              value={number} onChange={(event) => setNumber(event.target.value)}
              readOnly={phase !== "start"} required />
          </div>
          {phase === "start" && (
            <label style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
              <input type="checkbox" style={{ marginTop: 4 }} checked={consent} onChange={(event) => setConsent(event.target.checked)} required />
              <span>I agree to receive a verification text and voicemail alerts at this number.</span>
            </label>
          )}
          {phase === "confirm" && (
            <div>
              <label className={styles.formLabel} htmlFor="daytello-owner-code">Six-digit verification code</label>
              <input id="daytello-owner-code" className={styles.textInput} inputMode="numeric"
                autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6}
                style={{ borderColor: "#3b82f6", backgroundColor: "#eff6ff", maxWidth: 240 }}
                value={code} onChange={(event) => setCode(event.target.value)} required />
            </div>
          )}
          {phase === "save" && <p role="status">Phone verified. Save to turn on forwarding and voicemail texts.</p>}
          {error && <p role="alert">{error}</p>}
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 12 }}>
            <button type="submit" className={styles.continueButton} disabled={busy}>
              {busy ? "Please wait…" : phase === "start" ? "Send Verification Code" : phase === "confirm" ? "Verify Phone" : "Save Forwarding & Voicemail Texts"}
            </button>
            {phase === "confirm" && (
              <button type="button" disabled={busy} onClick={() => { setCode(""); setError(""); setPhase("start"); }}>Change number or resend</button>
            )}
          </div>
        </form>
      )}
    </section>
  );
}
