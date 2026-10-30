import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { serverApiBase } from "@/lib/server-api-base";

export const dynamic = "force-dynamic";

// Preview-only bridge. The backend authenticates the owner and enforces
// shop isolation, SMS consent, OTP expiry, throttling, and one-time use.
export async function POST(request) {
  const origin = request.headers.get("origin");
  if (
    process.env.VERCEL_ENV !== "preview" ||
    process.env.VERCEL_GIT_COMMIT_REF !== "feature/daytello-general-voicemail-onboarding-20261029" ||
    origin !== new URL(request.url).origin
  ) {
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
  if (typeof phone !== "string" || !/^\\+1[2-9][0-9]{2}[2-9][0-9]{6}$/.test(phone)) {
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
