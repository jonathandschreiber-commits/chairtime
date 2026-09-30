import { cookies } from "next/headers";
import { NextResponse } from "next/server";


const API_BASE =
  "https://chairtime-production-94da.up.railway.app";


async function getToken() {
  const cookieStore = await cookies();

  return cookieStore.get(
    "chairtime_token"
  )?.value;
}


function unauthorizedResponse() {
  return NextResponse.json(
    {
      detail: "Not authenticated.",
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
    const token = await getToken();

    if (!token) {
      return unauthorizedResponse();
    }

    const { shopSlug } =
      await context.params;

    const response = await fetch(
      `${API_BASE}/api/shops/${encodeURIComponent(
        shopSlug
      )}`,
      {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/json",
        },
        cache: "no-store",
      }
    );

    const data = await response
      .json()
      .catch(() => ({}));

    return NextResponse.json(
      data,
      {
        status: response.status,
      }
    );
  } catch (error) {
    console.error(
      "Load shop proxy error:",
      error
    );

    return NextResponse.json(
      {
        detail:
          "Could not load shop.",
      },
      {
        status: 500,
      }
    );
  }
}
