import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { serverApiBase } from "@/lib/server-api-base";

export const dynamic = "force-dynamic";

export async function POST(request) {
  if (
    process.env.VERCEL_ENV !== "preview" ||
    process.env.VERCEL_GIT_COMMIT_REF !== "feature/daytello-voicemail-owner-sms-20261027" ||
    request.headers.get("origin") !== new URL(request.url).origin
  ) {
    return NextResponse.json({ detail: "Not found" }, { status: 404 });
  }

  const token = (await cookies()).get("chairtime_token")?.value;
  if (!token) {
    return NextResponse.json({ detail: "Sign in as Bob's test owner." }, { status: 401 });
  }

  try {
    const response = await fetch(
      `${serverApiBase()}/api/shops/bobs-shop/voicemail-notifications/activate-test`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({ confirmed_live_call_test: true }),
        cache: "no-store",
      }
    );
    const data = await response.json().catch(() => ({ detail: "Activation response unavailable." }));
    return NextResponse.json(data, {
      status: response.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json(
      { detail: "Unable to activate Bob's voicemail notifications." },
      { status: 502, headers: { "Cache-Control": "no-store" } }
    );
  }
}
