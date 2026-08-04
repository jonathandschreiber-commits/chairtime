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

async function getToken() {
  const cookieStore = await cookies();
  return cookieStore.get(COOKIE_NAME)?.value;
}

export async function GET() {
  const token = await getToken();

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

  try {
    const backendResponse = await fetch(
      `${API_URL}/api/admin/blocked-times`,
      {
        method: "GET",
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
            "Blocked times could not be loaded.",
        },
        {
          status: backendResponse.status,
        }
      );
    }

    return NextResponse.json({
      success: true,
      blocked_times: Array.isArray(backendData)
        ? backendData
        : [],
    });
  } catch (error) {
    console.error("Blocked-time GET route failed:", error);

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

export async function POST(request) {
  const token = await getToken();

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
        error: "Blocked-time details are required.",
      },
      {
        status: 400,
      }
    );
  }

  const barberId = body?.barber_id;
  const reason = String(body?.reason || "").trim();
  const startDatetime = body?.start_datetime;
  const endDatetime = body?.end_datetime;

  if (
    !barberId ||
    !reason ||
    !startDatetime ||
    !endDatetime
  ) {
    return NextResponse.json(
      {
        success: false,
        error:
          "Staff, reason, start time, and end time are required.",
      },
      {
        status: 400,
      }
    );
  }

  try {
    const backendResponse = await fetch(
      `${API_URL}/api/admin/blocked-times`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          barber_id: barberId,
          reason,
          start_datetime: startDatetime,
          end_datetime: endDatetime,
        }),
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
            "Blocked time could not be created.",
        },
        {
          status: backendResponse.status,
        }
      );
    }

    return NextResponse.json({
      success: true,
      blocked_time: backendData,
    });
  } catch (error) {
    console.error("Blocked-time POST route failed:", error);

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