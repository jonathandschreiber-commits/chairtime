import { cookies } from "next/headers";

const API_BASE =
  "https://chairtime-production-94da.up.railway.app";

export async function POST(request, context) {
  try {
    const { shopSlug } = await context.params;

    const cookieStore = await cookies();
    const token = cookieStore.get(
      "chairtime_token"
    )?.value;

    if (!token) {
      return Response.json(
        {
          detail: "Not authenticated",
        },
        {
          status: 401,
        }
      );
    }

    const body = await request
      .json()
      .catch(() => ({}));

    const response = await fetch(
      `${API_BASE}/api/services`,
      {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          ...body,
          shop_slug: shopSlug,
        }),
        cache: "no-store",
      }
    );

    const data = await response
      .json()
      .catch(() => ({}));

    return Response.json(
      data,
      {
        status: response.status,
      }
    );
  } catch (error) {
    console.error(
      "Create service proxy error:",
      error
    );

    return Response.json(
      {
        detail:
          "Could not add service.",
      },
      {
        status: 500,
      }
    );
  }
}
