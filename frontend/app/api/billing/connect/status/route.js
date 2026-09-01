import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const API_BASE =
  process.env.CHAIRTIME_API_URL ||
  "https://chairtime-production-94da.up.railway.app";

export async function GET() {
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
      `${API_BASE}/api/billing/connect/status`,
      {
        method: "GET",
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
            "Could not check payment account status.",
        },
        {
          status: response.status,
        }
      );
    }

    return NextResponse.json(data);
  } catch (error) {
    console.error(
      "Connect status proxy error:",
      error
    );

    return NextResponse.json(
      {
        error:
          "Could not check payment account status.",
      },
      {
        status: 500,
      }
    );
  }
}
