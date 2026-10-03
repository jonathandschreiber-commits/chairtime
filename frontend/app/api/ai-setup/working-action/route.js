import { cookies } from "next/headers";

const BACKEND_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "https://chairtime-production-94da.up.railway.app"
).replace(/\/$/, "");

export const dynamic = "force-dynamic";

const ACTION_NAMES = new Set([
  "get_shop_information_v2",
  "check_availability",
  "check_availability_v2",
  "book_appointment",
]);

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

export async function GET(request) {
  try {
    const name = new URL(request.url).searchParams.get("action_name") ||
      "get_shop_information_v2";
    if (!ACTION_NAMES.has(name)) {
      return json({ detail: "Unknown receptionist action name." }, 400);
    }
    const cookieStore = await cookies();
    const token = cookieStore.get("chairtime_token")?.value;
    if (!token) {
      return json({ detail: "Please sign in as this shop's owner." }, 401);
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
    // The authenticated backend chooses the shop. No query may select a shop
    // or another shop's agent, even if the owner has several browser tabs open.
    const current = await read("/provision/status");
    const slug = current.chairtime_shop?.slug;
    const shopId = current.chairtime_shop?.id;
    const agentId = current.agent?.id;
    if (!slug || !shopId || !agentId) {
      return json({ detail: "This shop's AI agent could not be found." }, 409);
    }
    const saved = await read(`/agents/${encodeURIComponent(agentId)}`);
    if (saved.chairtime_shop?.slug !== slug ||
        saved.chairtime_shop?.id !== shopId || saved.agent?.id !== agentId) {
      return json({ detail: "The returned agent did not match the signed-in shop." }, 409);
    }
    const actions = saved.agent?.actions;
    const matches = Array.isArray(actions) ? actions.filter(
      (item) => item.name === name
    ) : [];
    if (matches.length !== 1) {
      return json({ detail: "The selected action is missing or duplicated.",
        shop_slug: slug, action_name: name, matching_actions: matches.length }, 409);
    }
    const action = matches[0];
    const parameters = action.action_parameters || action.actionParameters || {};
    const type = action.action_type || action.actionType;
    const endpoint = type === "CAP"
      ? parameters.schemaValues?.requestBodyValues?.webhookUrl?.value
      : parameters.apiDetails?.url;
    const suffix = name === "get_shop_information_v2" ? "shop-information"
      : name.startsWith("check_availability") ? "availability" : "book";
    const expectedEndpoint = `${BACKEND_URL}/api/ai-setup/tenant-webhook/${encodeURIComponent(slug)}/${suffix}`;
    return json({
      success: true,
      shop_slug: slug,
      agent_id: agentId,
      action_name: name,
      endpoint_matches_shop: endpoint === expectedEndpoint,
      stored_endpoint: endpoint || null,
      expected_endpoint: expectedEndpoint,
      cap_definition_id: parameters.capActionId || null,
      action: redact(action),
    });
  } catch (error) {
    return json({
      detail: "Could not export the saved settings. Please share this error status.",
    }, Number.isInteger(error?.status) ? error.status : 502);
  }
}
