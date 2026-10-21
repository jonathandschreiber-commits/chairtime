import { serverApiBase } from "@/lib/server-api-base";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";
 
// Same authenticated Railway proxy pattern as the existing AI setup routes.
const BACKEND_URL = serverApiBase();
 
export const dynamic = "force-dynamic";
 
async function forwardStaffTransfer(method, request) {
  try {
    const cookieStore = await cookies();
    const token = cookieStore.get("chairtime_token")?.value;
    if (!token) {
      return NextResponse.json(
        { detail: "Please sign in to your DayTello shop account." },
        { status: 401, headers: { "Cache-Control": "no-store" } }
      );
    }
 
    const options = {
      method,
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
      },
      cache: "no-store",
    };
    if (method === "POST") {
      let submitted;
      try {
        submitted = await request.json();
      } catch {
        return NextResponse.json(
          { detail: "Please provide valid call-transfer settings." },
          { status: 400 }
        );
      }
      if (!submitted || typeof submitted !== "object" ||
        Array.isArray(submitted) || typeof submitted.enabled !== "boolean") {
        return NextResponse.json(
          { detail: "Select whether live transfers are enabled." },
          { status: 400 }
        );
      }
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify({
        enabled: submitted.enabled,
        phone_number: submitted.enabled ? submitted.phone_number : null,
        confirm_no_forwarding_loop: Boolean(submitted.confirm_no_forwarding_loop),
      });
    }
 
    const backend = await fetch(`${BACKEND_URL}/api/ai-setup/staff-transfer`, options);
    const data = await backend.json().catch(() => ({
      detail: "The AI transfer service returned an invalid response.",
    }));
    return NextResponse.json(data, {
      status: backend.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch (error) {
    console.error("DayTello staff transfer proxy error", error);
    return NextResponse.json(
      { detail: "Could not contact the AI call-transfer service." },
      { status: 502, headers: { "Cache-Control": "no-store" } }
    );
  }
}
 
export async function GET() {
  return forwardStaffTransfer("GET");
}
 
export async function POST(request) {
  return forwardStaffTransfer("POST", request);
}
