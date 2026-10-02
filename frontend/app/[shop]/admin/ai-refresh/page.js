"use client";

import { useState } from "react";
import { useParams } from "next/navigation";

export default function UpdateAiReceptionistPage() {
  const { shop } = useParams();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function updateReceptionist() {
    if (busy) return;
    setBusy(true);
    setMessage("");
    try {
      const status = await fetch("/api/ai-setup/provision/status", {
        cache: "no-store",
      });
      const current = await status.json();
      if (!status.ok) {
        throw new Error("Please sign in as this shop's owner and try again.");
      }
      if (current.chairtime_shop?.slug !== shop) {
        throw new Error("Please sign in as this shop's owner.");
      }
      if (!current.provisioned) {
        throw new Error("Please finish setting up the AI receptionist first.");
      }
      const response = await fetch("/api/ai-setup/provision", {
        method: "POST",
        headers: { Accept: "application/json" },
      });
      const result = await response.json();
      if (!response.ok || !result.success) {
        const detail = typeof result.detail === "string"
          ? result.detail : result.detail?.message;
        throw new Error(detail || "Could not update the receptionist. Please try again.");
      }
      setMessage("Your receptionist is updated. Please make a test call.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main style={{ maxWidth: 560, margin: "60px auto", padding: 24,
      fontFamily: "Arial, sans-serif", lineHeight: 1.5 }}>
      <h1>Update AI receptionist</h1>
      <p>Connect your receptionist to this shop's current services,
        staff, prices, hours, and availability.</p>
      <button onClick={updateReceptionist} disabled={busy}
        style={{ padding: "12px 20px", fontSize: 16, cursor: "pointer" }}>
        {busy ? "Updating..." : "Update receptionist"}
      </button>
      {message && <p role="status">{message}</p>}
      <p><a href={`/${shop}/admin`}>Back to admin</a></p>
    </main>
  );
}

