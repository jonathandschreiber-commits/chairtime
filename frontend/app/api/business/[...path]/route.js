import { cookies } from "next/headers";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

async function proxy(request, { params }, method) {
  try {
    const token = (await cookies()).get("chairtime_token")?.value;
    if (!token) return Response.json({ detail: "Please sign in." }, { status: 401 });
    const parts = (await params).path;
    const path = Array.isArray(parts) ? parts.join("/") : "";
    const allowed = (method === "GET" && ["report", "highlevel-test"].includes(path)) ||
      (method === "POST" && path === "expenses") ||
      (method === "PATCH" && /^expenses\/[a-zA-Z0-9-]+\/void$/.test(path));
    if (!allowed) return Response.json({ detail: "Unknown report endpoint." }, { status: 404 });
    // Mutations require the browser's same-origin session, as well as backend admin authorization.
    if (method !== "GET" && request.headers.get("origin") !== new URL(request.url).origin) {
      return Response.json({ detail: "Invalid request origin." }, { status: 403 });
    }
    const base = process.env.CHAIRTIME_API_URL?.replace(/\/+$/, "");
    if (!base) return Response.json({ detail: "Backend URL is not configured." }, { status: 503 });
    const response = await fetch(`${base}/api/business/${path}${new URL(request.url).search}`, {
      method, headers: { Authorization: `Bearer ${token}`, Accept: "application/json", "Content-Type": "application/json" },
      ...(method !== "GET" ? { body: await request.text() } : {}),
      cache: "no-store", signal: AbortSignal.timeout(55000),
    });
    let result;
    try { result = await response.json(); }
    catch { result = { detail: "The report service returned an invalid response." }; }
    return Response.json(result, { status: response.status, headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ detail: "The report service could not be reached. Refresh to try again." }, { status: 502 });
  }
}
export async function GET(request, context) { return proxy(request, context, "GET"); }
export async function POST(request, context) { return proxy(request, context, "POST"); }
export async function PATCH(request, context) { return proxy(request, context, "PATCH"); }
