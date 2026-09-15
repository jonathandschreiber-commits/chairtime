import { NextResponse } from "next/server";
import { cookies } from "next/headers";

const COOKIE_NAME = "chairtime_token";

export async function PATCH(request) {
  try {
    const apiUrl = process.env.CHAIRTIME_API_URL;

    if (!apiUrl) {
      return NextResponse.json(
        { detail: "Backend URL is not configured." },
        { status: 500 }
      );
    }

    const cookieStore = await cookies();
    const token = cookieStore.get(COOKIE_NAME)?.value;

    if (!token) {
      return NextResponse.json(
        { detail: "Not authenticated." },
        { status: 401 }
      );
    }

    const body = await request.json();

    const customerPhone = String(
      body.customer_phone || ""
    ).trim();

    const customerTags = String(
      body.customer_tags ?? ""
    );

    const params = new URLSearchParams({
      customer_phone: customerPhone,
      customer_tags: customerTags,
    });

    const response = await fetch(
      `${apiUrl}/api/customers/tags?${params.toString()}`,
      {
        method: "PATCH",
        headers: {
          Accept: "application/json",
          Authorization: `Bearer ${token}`,
        },
        cache: "no-store",
      }
    );

    let data;

    try {
      data = await response.json();
    } catch {
      data = {
        detail: "The backend returned an invalid response.",
      };
    }

    return NextResponse.json(data, {
      status: response.status,
    });
  } catch (error) {
    console.error(
      "Customer tags proxy error:",
      error
    );

    return NextResponse.json(
      {
        detail: "Unable to update customer tags.",
      },
      { status: 500 }
    );
  }
}
