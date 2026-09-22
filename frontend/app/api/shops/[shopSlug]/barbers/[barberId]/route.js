import { cookies } from "next/headers";

const API_BASE =
  "https://chairtime-production-94da.up.railway.app";

async function getToken() {
  const cookieStore = await cookies();

  return cookieStore.get(
    "chairtime_token"
  )?.value;
}

async function proxyResponse(response) {
  const data = await response
    .json()
    .catch(() => ({}));

  return Response.json(
    data,
    {
      status: response.status,
    }
  );
}

export async function PATCH(request, context) {
  try {
    const {
      shopSlug,
      barberId,
    } = await context.params;

    const token = await getToken();

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
      `${API_BASE}/api/barbers/${encodeURIComponent(
        barberId
      )}`,
      {
        method: "PATCH",
        headers: {
          Accept: "application/json",
          "Content-Type":
            "application/json",
          Authorization:
            `Bearer ${token}`,
        },
        body: JSON.stringify({
          ...body,
          shop_slug: shopSlug,
        }),
        cache: "no-store",
      }
    );

    return proxyResponse(response);
  } catch (error) {
    console.error(
      "Update staff proxy error:",
      error
    );

    return Response.json(
      {
        detail:
          "Could not update staff member.",
      },
      {
        status: 500,
      }
    );
  }
}

export async function DELETE(
  request,
  context
) {
  try {
    const {
      shopSlug,
      barberId,
    } = await context.params;

    const token = await getToken();

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

    const response = await fetch(
      `${API_BASE}/api/barbers/${encodeURIComponent(
        barberId
      )}?shop_slug=${encodeURIComponent(
        shopSlug
      )}`,
      {
        method: "DELETE",
        headers: {
          Accept: "application/json",
          Authorization:
            `Bearer ${token}`,
        },
        cache: "no-store",
      }
    );

    return proxyResponse(response);
  } catch (error) {
    console.error(
      "Delete staff proxy error:",
      error
    );

    return Response.json(
      {
        detail:
          "Could not delete staff member.",
      },
      {
        status: 500,
      }
    );
  }
}
