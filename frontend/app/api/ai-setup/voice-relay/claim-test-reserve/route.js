import { serverApiBase } from "@/lib/server-api-base";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function POST() {
  try {
    const token = (await cookies()).get("chairtime_token")?.value;
    if (!token) {
      return NextResponse.json({ detail: "Please sign in." }, { status: 401 });
    }
    const response = await fetch(
      `${serverApiBase()}/api/shops/test-shop-3/voice-relay/claim-test-reserve`,
      {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
        cache: "no-store",
      }
    );
    const data = await response.json().catch(() => ({ detail: "Relay registration unavailable." }));
    return NextResponse.json(data, {
      status: response.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json({ detail: "Relay registration unavailable." }, { status: 502 });
  }
}
