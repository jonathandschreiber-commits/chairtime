"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

// Not linked from the public site. The API refuses non-Preview requests and
// requires a one-time invitation configured only on the isolated test server.
export default function TestOwnerEnrollmentPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [invite, setInvite] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  async function submit(event) {
    event.preventDefault();
    if (saving) return;
    setMessage("");
    setSaving(true);
    try {
      const response = await fetch("/api/auth/test-claim-existing-shop", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        cache: "no-store",
        body: JSON.stringify({
          owner_name: name.trim(),
          email: email.trim().toLowerCase(),
          password,
          invite_code: invite.trim(),
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || "Unable to enroll test owner.");
      }
      setPassword("");
      setInvite("");
      router.replace("/bobs-shop/admin/ai-receptionist");
      router.refresh();
    } catch (error) {
      setMessage(error.message || "Unable to enroll test owner.");
    } finally {
      setSaving(false);
    }
  }

  const input = "block w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-slate-900 focus:border-indigo-600 focus:outline-none";
  const label = "block mb-1.5 text-sm font-semibold text-slate-800";

  return (
    <main className="min-h-screen bg-slate-50 px-5 py-12">
      <section className="mx-auto max-w-md rounded-2xl border border-slate-200 bg-white p-7 shadow-sm">
        <p className="text-sm font-bold uppercase tracking-wide text-indigo-700">DayTello isolated test</p>
        <h1 className="mt-2 text-2xl font-bold text-slate-900">Bob's Shop — Owner access</h1>
        <p className="mt-3 text-sm leading-6 text-slate-600">
          This one-time test enrollment links your login to the existing Bob's Shop
          and preserves its voicemail history. Use a new test-only password,
          not your live DayTello password. No payment is required.
        </p>
        {message ? <p role="alert" className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-800">{message}</p> : null}
        <form onSubmit={submit} className="mt-6 space-y-4">
          <div>
            <label htmlFor="owner-name" className={label}>Your name</label>
            <input id="owner-name" className={input} value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} autoComplete="name" />
          </div>
          <div>
            <label htmlFor="owner-email" className={label}>Test owner email</label>
            <input id="owner-email" className={input} type="email" value={email} onChange={(e) => setEmail(e.target.value)} required maxLength={254} autoComplete="email" />
          </div>
          <div>
            <label htmlFor="owner-password" className={label}>New test password (12 or more characters)</label>
            <input id="owner-password" className={input} type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={12} maxLength={72} autoComplete="new-password" />
          </div>
          <div>
            <label htmlFor="owner-invite" className={label}>One-time invitation code</label>
            <input id="owner-invite" className={input} type="password" value={invite} onChange={(e) => setInvite(e.target.value)} required autoComplete="off" />
          </div>
          <button type="submit" disabled={saving} className="w-full rounded-xl bg-slate-900 px-5 py-3 font-bold text-white disabled:opacity-50">
            {saving ? "Setting up owner login…" : "Access Bob's existing Shop"}
          </button>
        </form>
        <p className="mt-5 text-xs text-slate-500">
          Test environment only. The invitation works once, and cannot be
          used to create or claim any other business.
        </p>
      </section>
    </main>
  );
}
