import { cookies } from "next/headers";
import { getBackendUrl } from "../../../../../../lib/backend-url.js";

export async function DELETE(request, { params }) {
  const token = (await cookies()).get("chairtime_token")?.value;
  if (!token) {
    return Response.json({ detail: "Not authenticated." }, { status: 401 });
  }

  const { ruleId } = await params;
  try {
    const response = await fetch(
      `${getBackendUrl()}/api/shop-availability-rules/${encodeURIComponent(ruleId)}`,
      {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
        cache: "no-store",
      },
    );
    const data = await response.json().catch(() => ({}));
    return Response.json(data, { status: response.status });
  } catch (error) {
    console.error("Shop hours delete proxy error:", error);
    return Response.json({ detail: "Could not update your shop hours." }, { status: 502 });
  }
}
