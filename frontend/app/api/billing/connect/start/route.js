import { getBackendUrl } from "../../../../../lib/backend-url.js";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";



export async function POST() {
  try {
    const cookieStore = await cookies();

    const token = cookieStore.get(
      "chairtime_token"
    )?.value;

    if (!token) {
      return NextResponse.json(
        {
          error: "Not authenticated.",
        },
        {
          status: 401,
        }
      );
    }

    const response = await fetch(
      `${getBackendUrl()}/api/billing/connect/start`,
      {
        method: "POST",
        headers: {
          Accept: "application/json",
          Authorization: `Bearer ${token}`,
        },
        cache: "no-store",
      }
    );

    let data = {};

    try {
      data = await response.json();
    } catch {
      data = {};
    }

    if (!response.ok) {
      return NextResponse.json(
        {
          error:
            data.detail ||
            data.error ||
            "Could not start Stripe setup.",
        },
        {
          status: response.status,
        }
      );
    }

    return NextResponse.json(data);
  } catch (error) {
    console.error(
      "Connect start proxy error:",
      error
    );

    return NextResponse.json(
      {
        error:
          "Could not start Stripe setup.",
      },
      {
        status: 500,
      }
    );
  }
}
