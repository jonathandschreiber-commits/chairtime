import { cookies } from "next/headers";

const API_BASE =
  "https://chairtime-production-94da.up.railway.app";

export async function POST(request, { params }) {
  try {
    const { shopSlug } = await params;

    const cookieStore = await cookies();
    const token = cookieStore.get("chairtime_token")?.value;

    if (!token) {
      return Response.json(
        { detail: "Not authenticated." },
        { status: 401 }
      );
    }

    const body = await request.json();

    const response = await fetch(
      `${API_BASE}/api/admin/blocked-times`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          ...body,
          shop_slug: shopSlug,
        }),
        cache: "no-store",
      }
    );

    const text = await response.text();

    return new Response(text, {
      status: response.status,
      headers: {
        "Content-Type":
          response.headers.get("Content-Type") ||
          "application/json",
      },
    });
  } catch (error) {
    console.error(
      "Blocked time proxy POST error:",
      error
    );

    return Response.json(
      { detail: "Could not create blocked time." },
      { status: 500 }
    );
  }
}
