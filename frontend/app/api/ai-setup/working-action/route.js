import { cookies } from "next/headers";

const BACKEND_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "https://chairtime-production-94da.up.railway.app"
).replace(/\/$/, "");

export const dynamic = "force-dynamic";

function redact(value) {
  if (Array.isArray(value)) return value.map(redact);
  if (!value || typeof value !== "object") return value;
  const result = {};
  const header = String(value.key || value.name || "");
  const sensitive = /secret|token|password|authorization|api.?key/i;
  for (const [key, item] of Object.entries(value)) {
    if (sensitive.test(key) ||
        (key === "value" && sensitive.test(header))) {
      result[key] = "[REDACTED]";
    } else {
      result[key] = redact(item);
    }
  }
  return result;
}

function json(data, status = 200) {
  return Response.json(data, {
    status,
    headers: { "Cache-Control": "no-store" },
  });
}

export async function GET() {
  try {
    const cookieStore = await cookies();
    const token = cookieStore.get("chairtime_token")?.value;
    if (!token) {
      return json({ detail: "Please sign in as Bob's shop owner." }, 401);
    }
    async function read(path) {
      const response = await fetch(`${BACKEND_URL}/api/ai-setup${path}`, {
        method: "GET",
        headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
        cache: "no-store",
        signal: AbortSignal.timeout(20000),
      });
      if (!response.ok) {
        const failure = new Error("Could not read the saved AI settings.");
        failure.status = response.status;
        throw failure;
      }
      return response.json();
    }
    const current = await read("/provision/status");
    if (current.chairtime_shop?.slug !== "bobs-shop") {
      return json({ detail: "Please sign in as Bob's shop owner." }, 403);
    }
    const agentId = current.agent?.id;
    if (!agentId) {
      return json({ detail: "Bob's AI agent could not be found." }, 409);
    }
    const saved = await read(`/agents/${encodeURIComponent(agentId)}`);
    if (saved.chairtime_shop?.slug !== "bobs-shop") {
      return json({ detail: "The returned shop did not match Bob's shop." }, 409);
    }
    const actions = saved.agent?.actions;
    const action = Array.isArray(actions) ? actions.find(
      (item) => item.name === "get_shop_information_v2"
    ) : null;
    if (!action) {
      return json({ detail: "The working v2 action could not be found." }, 409);
    }
    return json({
      success: true,
      shop_slug: "bobs-shop",
      agent_id: agentId,
      action: redact(action),
    });
  } catch (error) {
    return json({
      detail: "Could not export the settings. Please share this error status.",
    }, Number.isInteger(error?.status) ? error.status : 502);
  }
}
