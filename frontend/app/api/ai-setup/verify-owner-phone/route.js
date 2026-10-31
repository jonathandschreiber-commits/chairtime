import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { serverApiBase } from "@/lib/server-api-base";
import { isValidUsOwnerPhone } from "@/lib/owner-phone.mjs";

export const dynamic = "force-dynamic";

// Preview-only bridge. Backend enforces owner/shop authorization, SMS
// consent, OTP expiry, throttling and one-time use.
function previewAllowed() {
  return process.env.VERCEL_ENV === "preview" &&
    process.env.VERCEL_GIT_COMMIT_REF === "feature/daytello-general-voicemail-onboarding-20261029";
}

export async function GET() {
  if (!previewAllowed()) return NextResponse.json({ detail: "Not found" }, { status: 404 });
  if (!(await cookies()).get("chairtime_token")?.value) {
    return NextResponse.json({ detail: "Please sign in." }, { status: 401 });
  }
  // UI availability is NOT proof of SMS delivery or live telephone readiness.
  return NextResponse.json({ preview_verification_ui_available: true },
    { headers: { "Cache-Control": "no-store" } });
}

export async function POST(request) {
  if (!previewAllowed() || request.headers.get("origin") !== new URL(request.url).origin) {
    return NextResponse.json({ detail: "Not found" }, { status: 404 });
  }

  const token = (await cookies()).get("chairtime_token")?.value;
  if (!token) {
    return NextResponse.json({ detail: "Please sign in." }, { status: 401 });
  }

  let payload;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid request." }, { status: 400 });
  }

  const { shop_slug: slug, phone_number: phone, action } = payload ?? {};
  if (typeof slug !== "string" || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)) {
    return NextResponse.json({ detail: "Invalid shop." }, { status: 400 });
  }
  // Opt-out is always explicit. It revokes the verified recipient and stops
  // owner texts, but cannot change provider call routing or voicemail capture.
  // Do not require a phone number to opt out: a lost phone must not trap an owner.
  if (action === "disable") {
    if (payload.confirm_disable_notifications !== true) {
      return NextResponse.json({ detail: "Confirm that voicemail texts should be disabled." }, { status: 409 });
    }
    try {
      const response = await fetch(
        `${serverApiBase()}/api/shops/${encodeURIComponent(slug)}/voicemail-owner/notifications/disable`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
          cache: "no-store",
        }
      );
      const data = await response.json().catch(() => ({ detail: "Could not disable voicemail texts." }));
      return NextResponse.json(data, {
        status: response.status,
        headers: { "Cache-Control": "no-store" },
      });
    } catch {
      return NextResponse.json({ detail: "Could not disable voicemail texts." }, { status: 502 });
    }
  }
  if (!isValidUsOwnerPhone(phone)) {
    return NextResponse.json({ detail: "Enter a valid +1 phone number." }, { status: 422 });
  }
  if (action !== "start" && action !== "confirm") {
    return NextResponse.json({ detail: "Invalid verification action." }, { status: 400 });
  }

  let backendBody;
  if (action === "start") {
    if (payload.consent_to_verification_sms !== true) {
      return NextResponse.json({ detail: "Consent to receive a verification text is required." }, { status: 409 });
    }
    backendBody = { phone_number: phone, consent_to_verification_sms: true };
  } else {
    if (typeof payload.code !== "string" || !/^[0-9]{6}$/.test(payload.code)) {
      return NextResponse.json({ detail: "Enter the six-digit code." }, { status: 422 });
    }
    backendBody = { phone_number: phone, code: payload.code };
  }

  try {
    const response = await fetch(
      `${serverApiBase()}/api/shops/${encodeURIComponent(slug)}/voicemail-owner/verification/${action}`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(backendBody),
        cache: "no-store",
      }
    );
    const data = await response.json().catch(() => ({ detail: "Verification service unavailable." }));
    return NextResponse.json(data, {
      status: response.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json({ detail: "Verification service unavailable." }, { status: 502 });
  }
}
