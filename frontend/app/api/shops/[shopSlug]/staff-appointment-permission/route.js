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
  const token = await getToken();

  if (!token) {
    return unauthorizedResponse();
  }

  const { shopSlug } =
    await context.params;

  const response = await fetch(
    `${API_BASE}/api/shops/${encodeURIComponent(
      shopSlug
    )}/staff-appointment-permission`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
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
}


export async function PATCH(
  request,
  context
) {
  const token = await getToken();

  if (!token) {
    return unauthorizedResponse();
  }

  const { shopSlug } =
    await context.params;

  const body = await request.json();

  const response = await fetch(
    `${API_BASE}/api/shops/${encodeURIComponent(
      shopSlug
    )}/staff-appointment-permission`,
    {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
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
}
