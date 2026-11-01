import { serverApiBase } from "@/lib/server-api-base";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

async function proxy(method, request) {
  try {
    const token = (await cookies()).get("chairtime_token")?.value;
    if (!token) {
      return NextResponse.json({ detail: "Please sign in." }, { status: 401 });
    }
    const body = method === "PUT" ? await request.json() : null;
    const shop = body?.shop_slug || new URL(request.url).searchParams.get("shop");
    if (!shop || !/^[a-z0-9-]+$/.test(shop)) {
      return NextResponse.json({ detail: "Invalid business." }, { status: 400 });
    }
    const response = await fetch(
      `${serverApiBase()}/api/shops/${encodeURIComponent(shop)}/call-voicemail-number`,
      {
        method,
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/json",
          ...(method === "PUT" ? { "Content-Type": "application/json" } : {}),
        },
        ...(method === "PUT" ? { body: JSON.stringify({ phone_number: body.phone_number }) } : {}),
        cache: "no-store",
      }
    );
    const data = await response.json().catch(() => ({ detail: "Call settings unavailable." }));
    return NextResponse.json(data, { status: response.status, headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ detail: "Unable to update call settings." }, { status: 502 });
  }
}

export async function GET(request) { return proxy("GET", request); }
export async function PUT(request) { return proxy("PUT", request); }
