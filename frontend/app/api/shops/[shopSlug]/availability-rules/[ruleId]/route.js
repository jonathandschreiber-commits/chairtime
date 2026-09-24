import { cookies } from "next/headers";

const API_BASE =
  "https://chairtime-production-94da.up.railway.app";

export async function DELETE(
  request,
  context
) {
  try {
    const {
      ruleId,
    } = await context.params;

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

    const response = await fetch(
      `${API_BASE}/api/availability-rules/${encodeURIComponent(
        ruleId
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
      "Delete staff availability proxy error:",
      error
    );

    return Response.json(
      {
        detail:
          "Could not delete staff availability.",
      },
      {
        status: 500,
      }
    );
  }
}
