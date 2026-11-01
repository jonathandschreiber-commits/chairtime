import { NextResponse } from "next/server";
import { serverApiBase } from "@/lib/server-api-base";

// A narrow, non-production proxy. The real authorization is the one-time
// invitation checked by the isolated backend and the ownerless shop record.
export async function POST(request) {
  if (
    process.env.VERCEL_ENV !== "preview" ||
    process.env.VERCEL_GIT_COMMIT_REF !==
      "feature/daytello-voicemail-owner-sms-20261027"
  ) {
    return NextResponse.json({ detail: "Not found" }, { status: 404 });
  }

  if (request.headers.get("origin") !== new URL(request.url).origin) {
    return NextResponse.json(
      { detail: "Invalid request origin" },
      { status: 403 }
    );
  }

  try {
    const form = await request.json();
    const response = await fetch(
      `${serverApiBase()}/api/auth/test-claim-existing-shop`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          owner_name: form.owner_name,
          email: form.email,
          password: form.password,
          invite_code: form.invite_code,
        }),
        cache: "no-store",
      }
    );
    const result = await response.json().catch(() => ({
      detail: "The test owner enrollment service could not be read.",
    }));
    if (!response.ok) {
      return NextResponse.json(
        { detail: result.detail || "Enrollment denied" },
        { status: response.status, headers: { "Cache-Control": "no-store" } }
      );
    }
    if (!result.access_token || result.user?.shop_slug !== "bobs-shop") {
      return NextResponse.json(
        { detail: "Enrollment response was incomplete" },
        { status: 502 }
      );
    }
    const reply = NextResponse.json(
      { success: true, user: result.user },
      { headers: { "Cache-Control": "no-store" } }
    );
    reply.cookies.set({
      name: "chairtime_token",
      value: result.access_token,
      httpOnly: true,
      secure: true,
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 24 * 7,
    });
    return reply;
  } catch {
    return NextResponse.json(
      { detail: "Unable to reach the test enrollment service" },
      { status: 502, headers: { "Cache-Control": "no-store" } }
    );
  }
}
