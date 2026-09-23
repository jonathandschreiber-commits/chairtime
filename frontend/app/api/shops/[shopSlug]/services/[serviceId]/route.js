import { cookies } from "next/headers";

const API_BASE =
  "https://chairtime-production-94da.up.railway.app";

async function getToken() {
  const cookieStore = await cookies();

  return cookieStore.get(
    "chairtime_token"
  )?.value;
}

export async function PATCH(request, context) {
  try {
    const { serviceId } = await context.params;

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
      `${API_BASE}/api/services/${encodeURIComponent(
        serviceId
      )}`,
      {
        method: "PATCH",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
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
      "Update service proxy error:",
      error
    );

    return Response.json(
      {
        detail:
          "Could not update service.",
      },
      {
        status: 500,
      }
    );
  }
}

export async function DELETE(request, context) {
  try {
    const { serviceId } = await context.params;

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
      `${API_BASE}/api/services/${encodeURIComponent(
        serviceId
      )}`,
      {
        method: "DELETE",
        headers: {
          Accept: "application/json",
          Authorization: `Bearer ${token}`,
        },
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
      "Delete service proxy error:",
      error
    );

    return Response.json(
      {
        detail:
          "Could not delete service.",
      },
      {
        status: 500,
      }
    );
  }
}
