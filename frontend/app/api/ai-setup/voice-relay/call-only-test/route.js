import { serverApiBase } from "@/lib/server-api-base";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function POST(request) {
  try {
    const token = (await cookies()).get("chairtime_token")?.value;
    if (!token) return NextResponse.json({ detail: "Please sign in." }, { status: 401 });
    const payload = await request.json().catch(() => null);
    if (!payload || typeof payload.confirm_test_calls !== "boolean" ||
        Object.keys(payload).length !== 1) {
      return NextResponse.json({ detail: "Invalid test-call confirmation." }, { status: 400 });
    }
    const response = await fetch(
      `${serverApiBase()}/api/shops/test-shop-3/voice-relay/call-only-test`,
      {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        cache: "no-store",
      }
    );
    const data = await response.json().catch(() => ({ detail: "Test relay unavailable." }));
    return NextResponse.json(data, {
      status: response.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json({ detail: "Test relay unavailable." }, { status: 502 });
  }
}
