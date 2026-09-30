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


function unauthorizedResponse() {
  return Response.json(
    {
      detail: "Not authenticated",
    },
    {
      status: 401,
    }
  );
}


export async function GET(
  request,
  context
) {
  try {
    const { shopSlug } =
      await context.params;

    const token = await getToken();

    if (!token) {
      return unauthorizedResponse();
    }

    const response = await fetch(
      `${API_BASE}/api/service-catalog?shop_slug=${encodeURIComponent(
        shopSlug
      )}`,
      {
        method: "GET",
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
      "Load service catalog proxy error:",
      error
    );

    return Response.json(
      {
        detail:
          "Could not load service catalog.",
      },
      {
        status: 500,
      }
    );
  }
}


export async function POST(
  request,
  context
) {
  try {
    const { shopSlug } =
      await context.params;

    const token = await getToken();

    if (!token) {
      return unauthorizedResponse();
    }

    const body = await request
      .json()
      .catch(() => ({}));

    const response = await fetch(
      `${API_BASE}/api/service-catalog`,
      {
        method: "POST",
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
      "Create service catalog proxy error:",
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
