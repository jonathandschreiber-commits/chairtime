import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { serverApiBase } from "@/lib/server-api-base";

export async function DELETE(_request, { params }) {
  const token = (await cookies()).get("chairtime_token")?.value;
  if (!token) {
    return NextResponse.json({ detail: "Not authenticated." }, { status: 401 });
  }

  const { shopSlug, ruleId } = await params;
  if (!shopSlug || !ruleId) {
    return NextResponse.json({ detail: "Missing shop or rule." }, { status: 400 });
  }

  try {
    const response = await fetch(
      `${serverApiBase()}/api/shop-availability-rules/${encodeURIComponent(ruleId)}?shop_slug=${encodeURIComponent(shopSlug)}`,
      {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
        cache: "no-store",
      }
    );
    const body = await response.text();
    if (response.status === 204 || !body) return new Response(null, { status: response.status });
    let data;
    try { data = JSON.parse(body); } catch { data = { detail: "Unable to delete shop hours." }; }
    return NextResponse.json(data, { status: response.status });
  } catch {
    return NextResponse.json({ detail: "Could not update your shop hours." }, { status: 502 });
  }
}
