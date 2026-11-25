import { getBackendUrl } from "../../../../lib/backend-url.js";
import { cookies } from "next/headers";

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
      ((method === "GET" && (path.length === 2 || (path.length === 3 && path[2] === "manual-sessions"))) ||
       (method === "POST" && path.length === 3 && ["checkout", "text-link", "refund", "text-package-link", "package-expiration", "complete", "manual-sessions"].includes(path[2])));
    const packageOffers = path?.[0] === "packages" && (path.length === 1 ||
      (method === "POST" && path.length === 3 && /^[a-zA-Z0-9-]{1,100}$/.test(path[1]) &&
        ["edit", "delete"].includes(path[2])));
    const retail = path?.[0] === "retail" && (path.length === 1 ||
      (method === "GET" && path.length === 2 && path[1] === "customers"));
    const sales = path?.[0] === "sales" && (
      (method === "GET" && path.length === 1) ||
      (/^[a-zA-Z0-9-]{1,100}$/.test(path[1]) &&
        ((method === "GET" && path.length === 2) ||
          (method === "POST" && path.length === 3 && path[2] === "refund"))));
    if (!receipt && !appointment && !packageOffers && !retail && !sales) return json({ detail: "Payment endpoint not found." }, 404);
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
    if (retail && path[1] === "customers") query.set("q", new URL(request.url).searchParams.get("q") || "");
    if (sales) {
      const incoming = new URL(request.url).searchParams;
      for (const key of ["start", "end", "customer_phone", "customer_name"]) if (incoming.has(key)) query.set(key, incoming.get(key));
    }
    const endpoint = `${getBackendUrl()}/api/payments/${path.map(encodeURIComponent).join("/")}`;
    const sendsPackageData = method === "POST" && (retail || sales || (packageOffers && path[2] !== "delete") || ["text-package-link", "package-expiration", "complete", "manual-sessions"].includes(path[2]));
    const body = sendsPackageData ? JSON.stringify(await request.json()) : undefined;
    if (sendsPackageData) headers["Content-Type"] = "application/json";
    const response = await fetch(endpoint + (query.size ? `?${query}` : ""), {
      method, headers, body, cache: "no-store", signal: AbortSignal.timeout(30000),
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
