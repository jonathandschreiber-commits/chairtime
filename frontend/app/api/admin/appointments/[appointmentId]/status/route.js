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

export async function PATCH(request, context) {
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

  const { appointmentId } = await context.params;
  const body = await request.json();
  const appointmentStatus = body?.status;

  if (!appointmentStatus) {
    return NextResponse.json(
      {
        success: false,
        error: "Appointment status is required.",
      },
      {
        status: 400,
      }
    );
  }

  try {
    const backendResponse = await fetch(
      `${API_URL}/api/admin/appointments/${encodeURIComponent(
        appointmentId
      )}/status?appointment_status=${encodeURIComponent(
        appointmentStatus
      )}`,
      {
        method: "PATCH",
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
            "The appointment could not be updated.",
        },
        {
          status: backendResponse.status,
        }
      );
    }

    return NextResponse.json({
      success: true,
      appointment: backendData,
    });
  } catch (error) {
    console.error(
      "Appointment status route failed:",
      error
    );

    return NextResponse.json(
      {
        success: false,
        error: "The appointment service is unavailable.",
      },
      {
        status: 500,
      }
    );
  }
}