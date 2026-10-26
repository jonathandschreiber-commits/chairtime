import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { serverApiBase } from "@/lib/server-api-base";

export const dynamic = "force-dynamic";

// Never initiate a HighLevel test app connection from the live website.
export async function POST(request) {
  try {
    if (process.env.VERCEL_ENV !== "preview") {
      return NextResponse.json({ detail: "Available only in DayTello Preview." }, { status: 404 });
    }

    const origin = request.headers.get("origin");
    if (!origin || origin !== new URL(request.url).origin) {
      return NextResponse.json({ detail: "Invalid request origin." }, { status: 403 });
    }

    const token = (await cookies()).get("chairtime_token")?.value;
    if (!token) {
      return NextResponse.json({ detail: "Please sign in to the DayTello test account." }, { status: 401 });
    }

    const response = await fetch(`${serverApiBase()}/api/daytello/oauth/start`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
      },
      cache: "no-store",
    });
    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      return NextResponse.json(
        { detail: data.detail || "HighLevel testing authorization is not ready." },
        { status: response.status, headers: { "Cache-Control": "no-store" } },
      );
    }

    let destination;
    try {
      destination = new URL(data.authorization_url);
    } catch {
      destination = null;
    }
    if (
      !destination ||
      destination.protocol !== "https:" ||
      destination.hostname !== "marketplace.leadconnectorhq.com" ||
      destination.pathname !== "/v2/oauth/chooselocation"
    ) {
      return NextResponse.json(
        { detail: "Unexpected HighLevel authorization destination." },
        { status: 502, headers: { "Cache-Control": "no-store" } },
      );
    }

    return NextResponse.json(
      { authorization_url: destination.toString() },
      { status: 200, headers: { "Cache-Control": "no-store" } },
    );
  } catch (error) {
    console.error("DayTello test OAuth initiation failed:", error);
    return NextResponse.json(
      { detail: "Could not reach the DayTello test connection service." },
      { status: 502, headers: { "Cache-Control": "no-store" } },
    );
  }
}
