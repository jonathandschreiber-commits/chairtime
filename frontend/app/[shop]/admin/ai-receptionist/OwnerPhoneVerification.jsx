"use client";

import { useEffect, useState } from "react";
import { normalizeUsOwnerPhone } from "@/lib/owner-phone.mjs";

// Only appears when the branch-pinned, authenticated preview endpoint exists.
// This verifies SMS ownership; it does not save a transfer number or activate calls.
export default function OwnerPhoneVerification({ shopSlug, ownerNumber, onNotificationsDisabled }) {
  const [available, setAvailable] = useState(false);
  const [consent, setConsent] = useState(false);
  const [challengePhone, setChallengePhone] = useState("");
  const [verifiedPhone, setVerifiedPhone] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [confirmOptOut, setConfirmOptOut] = useState(false);

  const normalized = normalizeUsOwnerPhone(ownerNumber);

  // A locally verified badge must never survive an owner number/shop change.
  // Server-side possession proof is always scoped to one exact shop/number.
  useEffect(() => {
    setChallengePhone("");
    setVerifiedPhone("");
    setCode("");
    setConsent(false);
    setConfirmOptOut(false);
    setMessage("");
  }, [shopSlug, normalized]);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/ai-setup/verify-owner-phone", {
      credentials: "same-origin",
      cache: "no-store",
      signal: controller.signal,
    }).then(async (response) => {
      if (!response.ok) return;
      const result = await response.json();
      if (!controller.signal.aborted) {
        setAvailable(result.preview_verification_ui_available === true);
      }
    }).catch(() => {});
    return () => controller.abort();
  }, []);

  async function submit(action) {
    if (busy) return;
    if (!normalized) {
      setMessage("Enter a valid 10-digit US phone number above.");
      return;
    }
    if (action === "start" && !consent) {
      setMessage("Please consent to receiving the verification text.");
      return;
    }
    if (action === "confirm" && (challengePhone !== normalized || !/^[0-9]{6}$/.test(code))) {
      setMessage("Enter the six-digit code sent to this phone number.");
      return;
    }
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch("/api/ai-setup/verify-owner-phone", {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          shop_slug: shopSlug,
          phone_number: normalized,
          action,
          ...(action === "start"
            ? { consent_to_verification_sms: true }
            : { code }),
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Phone verification unavailable.");
      }
      if (action === "start") {
        setChallengePhone(normalized);
        setCode("");
        setVerifiedPhone("");
        setMessage("Verification text requested. Enter the code below.");
      } else if (data.owner_number_verified === true) {
        setVerifiedPhone(normalized);
        setChallengePhone("");
        setCode("");
        setMessage("Number verified. This does not activate voicemail, SMS alerts, or call routing.");
      } else {
        throw new Error("Verification was not confirmed.");
      }
    } catch (error) {
      setMessage(error?.message || "Phone verification unavailable.");
    } finally {
      setBusy(false);
    }
  }

  async function disableNotifications() {
    if (busy || !confirmOptOut) return;
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch("/api/ai-setup/verify-owner-phone", {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          shop_slug: shopSlug,
          action: "disable",
          confirm_disable_notifications: true,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || data.notifications_enabled !== false || data.owner_number_verified !== false) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Could not disable voicemail texts.");
      }
      setVerifiedPhone("");
      setChallengePhone("");
      setCode("");
      setConsent(false);
      setConfirmOptOut(false);
      onNotificationsDisabled?.();
      setMessage("Voicemail text notifications disabled. Call routing was not changed.");
    } catch (error) {
      setMessage(error?.message || "Could not disable voicemail texts.");
    } finally {
      setBusy(false);
    }
  }

  if (!available) return null;
  const awaitingCode = challengePhone === normalized && !verifiedPhone;
  const verified = verifiedPhone === normalized;

  return (
    <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-5 space-y-3">
      <h3 className="font-extrabold text-slate-900">Verify your phone — preview test</h3>
      <p className="text-sm text-slate-700">
        DayTello can send a one-time code to the phone number entered above.
        Verification alone does not turn on calls or voicemail notifications.
      </p>
      {verified ? (
        <p className="font-semibold text-emerald-800">✓ Phone number verified for this test.</p>
      ) : awaitingCode ? (
        <>
          <label htmlFor="voicemail-owner-code" className="block font-semibold text-slate-800">
            Six-digit verification code
          </label>
          <input id="voicemail-owner-code" inputMode="numeric" autoComplete="one-time-code"
            maxLength={6} pattern="[0-9]{6}" value={code}
            onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
            className="w-full rounded-lg border border-slate-300 p-3" />
          <button type="button" disabled={busy || code.length !== 6}
            onClick={() => submit("confirm")}
            className="rounded-lg bg-slate-900 px-5 py-3 font-bold text-white disabled:opacity-50">
            {busy ? "Checking…" : "Verify Code"}
          </button>
        </>
      ) : (
        <>
          <label className="flex items-start gap-3 text-sm text-slate-800">
            <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)}
              className="mt-1" />
            I agree to receive a one-time DayTello verification text at this number.
          </label>
          <button type="button" disabled={busy || !consent || !normalized}
            onClick={() => submit("start")}
            className="rounded-lg bg-slate-900 px-5 py-3 font-bold text-white disabled:opacity-50">
            {busy ? "Sending…" : "Text Verification Code"}
          </button>
        </>
      )}
      <div className="border-t border-amber-200 pt-3">
        <p className="text-sm text-slate-700">
          Stop receiving voicemail recording links? This only disables owner text
          notifications and revokes phone verification. It does not change calls.
        </p>
        {confirmOptOut ? (
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" disabled={busy} onClick={disableNotifications}
              className="rounded-lg bg-red-700 px-4 py-2 font-semibold text-white disabled:opacity-50">
              {busy ? "Disabling…" : "Confirm: Disable Voicemail Texts"}
            </button>
            <button type="button" disabled={busy} onClick={() => setConfirmOptOut(false)}
              className="rounded-lg border border-slate-300 px-4 py-2 font-semibold text-slate-800">
              Cancel
            </button>
          </div>
        ) : (
          <button type="button" disabled={busy} onClick={() => setConfirmOptOut(true)}
            className="mt-3 rounded-lg border border-red-300 px-4 py-2 font-semibold text-red-800 disabled:opacity-50">
            Disable Voicemail Texts
          </button>
        )}
      </div>
      {message && <p role="status" aria-live="polite" className="text-sm text-slate-800">{message}</p>}
    </div>
  );
}
