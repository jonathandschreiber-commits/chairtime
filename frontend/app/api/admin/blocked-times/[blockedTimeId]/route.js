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

export async function DELETE(request, context) {
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

  const { blockedTimeId } = await context.params;

  try {
    const backendResponse = await fetch(
      `${API_URL}/api/admin/blocked-times/${encodeURIComponent(
        blockedTimeId
      )}`,
      {
        method: "DELETE",
        headers: {
          Accept: "application/json",
          Authorization: `Bearer ${token}`,
        },
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
            "Blocked time could not be deleted.",
        },
        {
          status: backendResponse.status,
        }
      );
    }

    return NextResponse.json({
      success: true,
    });
  } catch (error) {
    console.error(
      "Blocked-time DELETE route failed:",
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