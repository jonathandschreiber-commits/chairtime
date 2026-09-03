import { NextResponse } from "next/server";
import { cookies } from "next/headers";

function getApiUrl() {
  const apiUrl = process.env.CHAIRTIME_API_URL;

  if (!apiUrl) {
    throw new Error(
      "CHAIRTIME_API_URL environment variable is missing."
    );
  }

  return apiUrl.replace(/\/+$/, "");
}

async function getAuthToken() {
  const cookieStore = await cookies();

  return (
    cookieStore.get("chairtime_token")?.value ||
    ""
  );
}

export async function POST(request) {
  try {
    const token = await getAuthToken();

    if (!token) {
      return NextResponse.json(
        {
          detail:
            "You must be signed in to start your free trial.",
        },
        {
          status: 401,
        }
      );
    }

    const apiUrl = getApiUrl();

    let body = {};

    try {
      body = await request.json();
    } catch {
      body = {};
    }

    const response = await fetch(
      `${apiUrl}/api/billing/create-checkout-session`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
        cache: "no-store",
      }
    );

    const responseText =
      await response.text();

    let data = {};

    if (responseText) {
      try {
        data = JSON.parse(responseText);
      } catch {
        data = {
          detail: responseText,
        };
      }
    }

    return NextResponse.json(
      data,
      {
        status: response.status,
      }
    );
  } catch (error) {
    console.error(
      "Checkout session proxy error:",
      error
    );

    return NextResponse.json(
      {
        detail:
          "Unable to start your free trial.",
      },
      {
        status: 500,
      }
    );
  }
}
