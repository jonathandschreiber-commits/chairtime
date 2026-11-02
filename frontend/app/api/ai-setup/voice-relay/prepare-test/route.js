import { cookies } from "next/headers";
import { serverApiBase } from "@/lib/server-api-base";

export async function POST(request) {
  try {
    const token = (await cookies()).get("chairtime_token")?.value;
    if (!token) {
      return Response.json({ detail: "Please sign in as the shop owner." }, { status: 401 });
    }
    const body = await request.json().catch(() => ({}));
    const shop = String(body.shop_slug || "");
    if (!/^[a-z0-9-]+$/.test(shop)) {
      return Response.json({ detail: "Invalid business." }, { status: 400 });
    }
    if (body.authorize_number_purchase !== true ||
        !/^[2-9][0-9]{2}$/.test(String(body.area_code || ""))) {
      return Response.json({ detail: "Confirm the number purchase and enter a valid area code." }, { status: 400 });
    }
    const response = await fetch(
      `${serverApiBase()}/api/shops/${encodeURIComponent(shop)}/voice-relay/prepare-test`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          area_code: body.area_code,
          authorize_number_purchase: true,
        }),
        cache: "no-store",
      }
    );
    const data = await response.json().catch(() => ({
      detail: "The voicemail relay service returned an invalid response.",
    }));
    return Response.json(data, {
      status: response.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch (error) {
    console.error("Voicemail relay preparation error:", error);
    return Response.json({ detail: "Could not prepare the voicemail relay number." }, { status: 502 });
  }
}
