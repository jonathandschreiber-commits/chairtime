import { cookies } from "next/headers";
export const dynamic = "force-dynamic";
const BACKEND = (process.env.CHAIRTIME_API_URL || "https://chairtime-production-94da.up.railway.app").replace(/\/+$/, "");
const json = (data, status = 200) => Response.json(data, {status, headers: {"Cache-Control": "no-store"}});
async function proxy(request, context, method) {
  try {
    const {path} = await context.params;
    if (!Array.isArray(path) || !/^[a-z0-9-]{1,100}$/.test(path[0] || "") ||
        !((path.length === 1 && ["GET", "PUT"].includes(method)) ||
          (path.length === 2 && path[1] === "reopen" && method === "POST")))
      return json({detail: "Timesheet endpoint not found."}, 404);
    if (method !== "GET") {
      const origin = request.headers.get("origin");
      if (origin && origin !== new URL(request.url).origin) return json({detail: "Invalid request origin."}, 403);
    }
    const token = (await cookies()).get("chairtime_token")?.value;
    if (!token) return json({detail: "Please sign in to view timesheets."}, 401);
    const week = new URL(request.url).searchParams.get("week_start") || "";
    if (!/^\d{4}-\d{2}-\d{2}$/.test(week)) return json({detail: "Choose a valid week."}, 400);
    const headers = {Accept: "application/json", Authorization: `Bearer ${token}`};
    const options = {method, headers, cache: "no-store", signal: AbortSignal.timeout(30000)};
    if (method !== "GET") {headers["Content-Type"] = "application/json"; options.body = await request.text();}
    const response = await fetch(`${BACKEND}/api/timesheets/${path.map(encodeURIComponent).join("/")}?week_start=${week}`, options);
    let data;
    try {data = await response.json();} catch {return json({detail: "The timesheet service returned an invalid response."}, 502);}
    return json(data, response.status);
  } catch {return json({detail: "Could not reach the timesheet service. Try again."}, 502);}
}
export function GET(request, context) {return proxy(request, context, "GET");}
export function PUT(request, context) {return proxy(request, context, "PUT");}
export function POST(request, context) {return proxy(request, context, "POST");}
