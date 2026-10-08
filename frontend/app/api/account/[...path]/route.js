import { cookies } from "next/headers";

const BACKEND = (process.env.CHAIRTIME_API_URL || process.env.NEXT_PUBLIC_API_BASE_URL ||
  "https://chairtime-production-94da.up.railway.app").replace(/\/$/, "");
export const dynamic = "force-dynamic";

function json(data, status = 200) {
  return Response.json(data, { status, headers: { "Cache-Control": "no-store" } });
}

async function proxy(request, context, method) {
  try {
    const { path } = await context.params;
    const receipt = method === "GET" && path?.length === 1 && path[0] === "receipt";
    const appointment = path?.[0] === "appointments" &&
      /^[a-zA-Z0-9-]{1,100}$/.test(path[1] || "") &&
      ((method === "GET" && path.length === 2) ||
       (method === "POST" && path.length === 3 && ["checkout", "text-link", "refund"].includes(path[2])));
    if (!receipt && !appointment) return json({ detail: "Payment endpoint not found." }, 404);
    if (method === "POST") {
      const origin = request.headers.get("origin");
      if (origin && origin !== new URL(request.url).origin) return json({ detail: "Invalid request origin." }, 403);
    }
    const headers = { Accept: "application/json" };
    if (!receipt) {
      const token = (await cookies()).get("chairtime_token")?.value;
      if (!token) return json({ detail: "Please sign in to collect payment." }, 401);
      headers.Authorization = `Bearer ${token}`;
    }
    const query = new URLSearchParams();
    if (receipt) {
      const incoming = new URL(request.url).searchParams;
      for (const key of ["token", "shop_slug"]) query.set(key, incoming.get(key) || "");
    }
    const response = await fetch(`${BACKEND}/api/payments/${path.map(encodeURIComponent).join("/")}${receipt ? `?${query}` : ""}`, {
      method, headers, cache: "no-store", signal: AbortSignal.timeout(30000),
    });
    let data;
    try { data = await response.json(); }
    catch { return json({ detail: "The payment service returned an invalid response." }, 502); }
    return json(data, response.status);
  } catch {
    return json({ detail: "Could not reach the payment service. Please refresh before trying again." }, 502);
  }
}

export function GET(request, context) { return proxy(request, context, "GET"); }
export function POST(request, context) { return proxy(request, context, "POST"); }
