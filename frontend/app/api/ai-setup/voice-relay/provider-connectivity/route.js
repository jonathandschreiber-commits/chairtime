import { cookies } from "next/headers";
import { serverApiBase } from "@/lib/server-api-base";

export const dynamic = "force-dynamic";

// Test Shop #3 only. Authentication and ownership are rechecked by FastAPI.
// This route has no write operations and never returns provider secrets.
export async function GET() {
  const token = (await cookies()).get("chairtime_token")?.value;
  if (!token) {
    return Response.json({ detail: "Please sign in as the shop owner." }, { status: 401 });
  }
  try {
    const response = await fetch(
      `${serverApiBase()}/api/shops/test-shop-3/voice-relay/provider-connectivity`,
      {
        method: "GET",
        headers: {
          Accept: "application/json",
          Authorization: `Bearer ${token}`,
        },
        cache: "no-store",
      }
    );
    if (response.status === 401 || response.status === 403) {
      return Response.json({ detail: "Please sign in as the Test Shop 3 owner." }, { status: response.status });
    }
    if (!response.ok) {
      return Response.json({ detail: "Twilio connectivity could not be verified." }, { status: response.status });
    }
    const data = await response.json();
    if (data?.connected !== true || !Number.isInteger(data?.assigned_number_count) || data.assigned_number_count < 0) {
      return Response.json({ detail: "Unexpected connectivity response." }, { status: 502 });
    }
    return Response.json({
      connected: true,
      assigned_number_count: data.assigned_number_count,
      live_relay_verified: false,
      ready_for_customer_calls: false,
    }, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ detail: "Twilio connectivity could not be verified." }, { status: 502 });
  }
}
