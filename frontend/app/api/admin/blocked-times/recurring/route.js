import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const COOKIE_NAME = "chairtime_token";

const API_URL =
  process.env.CHAIRTIME_API_URL ||
  "https://chairtime-production-94da.up.railway.app";

async function readJson(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

export async function POST(request) {
  const cookieStore = await cookies();
  const token = cookieStore.get(COOKIE_NAME)?.value;

  if (!token) {
    return NextResponse.json(
      {
        success: false,
        error: "Not authenticated.",
      },
      {
        status: 401,
      }
    );
  }

  let body;

  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      {
        success: false,
        error: "Recurring blocked-time details are required.",
      },
      {
        status: 400,
      }
    );
  }

  try {
    const backendResponse = await fetch(
      `${API_URL}/api/admin/blocked-times/recurring`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
        cache: "no-store",
      }
    );

    const backendData = await readJson(backendResponse);

    if (!backendResponse.ok) {
      return NextResponse.json(
        {
          success: false,
          error:
            backendData?.detail ||
            "Recurring blocked time could not be created.",
        },
        {
          status: backendResponse.status,
        }
      );
    }

    return NextResponse.json({
      success: true,
      ...backendData,
    });
  } catch (error) {
    console.error(
      "Recurring blocked-time route failed:",
      error
    );

    return NextResponse.json(
      {
        success: false,
        error: "The blocked-time service is unavailable.",
      },
      {
        status: 500,
      }
    );
  }
}