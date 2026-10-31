import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { serverApiBase } from "@/lib/server-api-base";

export const dynamic = "force-dynamic";

export async function POST(request) {
  if (
    process.env.VERCEL_ENV !== "preview" ||
    process.env.VERCEL_GIT_COMMIT_REF !== "feature/daytello-general-voicemail-onboarding-20261029" ||
    request.headers.get("origin") !== new URL(request.url).origin
  ) return NextResponse.json({ detail: "Not found" }, { status: 404 });

  const token = (await cookies()).get("chairtime_token")?.value;
  if (!token) return NextResponse.json({ detail: "Please sign in." }, { status: 401 });

  let body;
  try { body = await request.json(); } catch {
    return NextResponse.json({ detail: "Invalid request." }, { status: 400 });
  }
  const slug = body?.shop_slug;
  if (typeof slug !== "string" || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)) {
    return NextResponse.json({ detail: "Invalid shop." }, { status: 400 });
  }
  if (body?.confirmed_live_call_test !== true) {
    return NextResponse.json({ detail: "The completed call test must be confirmed." }, { status: 409 });
  }

  try {
    const response = await fetch(
      `${serverApiBase()}/api/shops/${encodeURIComponent(slug)}/voicemail-notifications/activate-test`,
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
    return NextResponse.json(data, { status: response.status, headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ detail: "Voicemail activation unavailable." }, { status: 502 });
  }
}
