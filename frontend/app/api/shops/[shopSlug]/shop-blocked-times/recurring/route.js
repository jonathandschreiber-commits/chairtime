import { getBackendUrl } from "../../../../../../lib/backend-url.js";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";





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


export async function POST(
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
    `${getBackendUrl()}/api/shop-blocked-times/recurring`,
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
