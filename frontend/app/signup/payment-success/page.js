"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

export default function PaymentSuccessPage() {
  const searchParams = useSearchParams();
  const sessionId = searchParams.get("session_id");

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "24px",
        background:
          "linear-gradient(135deg, #f8fafc 0%, #eef2f7 100%)",
      }}
    >
      <section
        style={{
          width: "100%",
          maxWidth: "560px",
          padding: "40px",
          background: "#ffffff",
          border: "1px solid #e5e7eb",
          borderRadius: "20px",
          boxShadow: "0 20px 50px rgba(15, 23, 42, 0.1)",
          textAlign: "center",
        }}
      >
        <div
          style={{
            width: "64px",
            height: "64px",
            margin: "0 auto 22px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            borderRadius: "50%",
            background: "#ecfdf5",
            color: "#047857",
            fontSize: "32px",
            fontWeight: "800",
          }}
        >
          ✓
        </div>

        <h1
          style={{
            margin: "0",
            color: "#111827",
            fontSize: "32px",
            fontWeight: "800",
            letterSpacing: "-0.6px",
          }}
        >
          Your free trial has started
        </h1>

        <p
          style={{
            margin: "16px auto 0",
            maxWidth: "460px",
            color: "#4b5563",
            fontSize: "17px",
            lineHeight: "1.6",
          }}
        >
          Your card is securely on file and you will not be charged today.
          Your scheduling plan is free for 30 days, then $49 per month.
        </p>

        <div
          style={{
            marginTop: "28px",
            padding: "18px",
            background: "#f9fafb",
            borderRadius: "12px",
            color: "#374151",
            fontSize: "15px",
            lineHeight: "1.6",
          }}
        >
          Next, finish setting up your business so customers can begin booking.
        </div>

        <Link
          href="/login"
          style={{
            display: "block",
            marginTop: "28px",
            padding: "14px 20px",
            color: "#ffffff",
            fontSize: "17px",
            fontWeight: "700",
            textDecoration: "none",
            background: "#111827",
            borderRadius: "10px",
          }}
        >
          Continue to Setup
        </Link>

        {sessionId ? (
          <p
            style={{
              margin: "18px 0 0",
              color: "#9ca3af",
              fontSize: "11px",
              wordBreak: "break-all",
            }}
          >
            Checkout confirmed.
          </p>
        ) : null}
      </section>
    </main>
  );
}
