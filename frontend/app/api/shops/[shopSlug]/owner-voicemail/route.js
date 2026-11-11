import { cookies } from "next/headers";
import { getBackendUrl } from "../../../../../lib/backend-url.js";

async function forward(context, path, method, body) {
  const token = (await cookies()).get("chairtime_token")?.value;
  if (!token) return Response.json({ detail: "Sign in to continue." }, { status: 401 });
  const { shopSlug } = await context.params;
  try {
    const response = await fetch(
      `${getBackendUrl()}/api/shops/${encodeURIComponent(shopSlug)}/${path}`,
      {
        method,
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
        cache: "no-store",
      },
    );
    return Response.json(await response.json().catch(() => ({})), { status: response.status });
  } catch {
    return Response.json({ detail: "Could not connect to voicemail setup. Try again." }, { status: 502 });
  }
}

export function GET(request, context) {
  return forward(context, "call-voicemail-number", "GET");
}

export async function POST(request, context) {
  const data = await request.json().catch(() => null);
  if (data?.action === "start") {
    return forward(context, "voicemail-owner/verification/start", "POST", {
      phone_number: data.phone_number,
      consent_to_verification_sms: data.consent === true,
    });
  }
  if (data?.action === "confirm") {
    return forward(context, "voicemail-owner/verification/confirm", "POST", {
      phone_number: data.phone_number,
      code: data.code,
    });
  }
  if (data?.action === "save") {
    return forward(context, "call-voicemail-number", "PUT", { phone_number: data.phone_number });
  }
  return Response.json({ detail: "Choose a valid setup action." }, { status: 400 });
}
