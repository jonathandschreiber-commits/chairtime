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

export async function GET() {
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

  const authorizationHeaders = {
    Accept: "application/json",
    Authorization: `Bearer ${token}`,
  };

  try {
    const meResponse = await fetch(
      `${API_URL}/api/auth/me`,
      {
        headers: authorizationHeaders,
        cache: "no-store",
      }
    );

    const user = await readJson(meResponse);

    if (!meResponse.ok || !user?.shop_slug) {
      return NextResponse.json(
        {
          success: false,
          error: "Your login has expired.",
        },
        {
          status: 401,
        }
      );
    }

    const shopSlug = user.shop_slug;

    const [
      appointmentsResponse,
      barbersResponse,
      servicesResponse,
    ] = await Promise.all([
      fetch(`${API_URL}/api/admin/appointments`, {
        headers: authorizationHeaders,
        cache: "no-store",
      }),
      fetch(
        `${API_URL}/api/barbers?shop_slug=${encodeURIComponent(
          shopSlug
        )}`,
        {
          headers: authorizationHeaders,
          cache: "no-store",
        }
      ),
      fetch(
        `${API_URL}/api/services?shop_slug=${encodeURIComponent(
          shopSlug
        )}`,
        {
          headers: authorizationHeaders,
          cache: "no-store",
        }
      ),
    ]);

    const [
      appointments,
      barbers,
      services,
    ] = await Promise.all([
      readJson(appointmentsResponse),
      readJson(barbersResponse),
      readJson(servicesResponse),
    ]);

    if (
      !appointmentsResponse.ok ||
      !barbersResponse.ok ||
      !servicesResponse.ok
    ) {
      return NextResponse.json(
        {
          success: false,
          error: "The agenda data could not be loaded.",
        },
        {
          status: 502,
        }
      );
    }

    return NextResponse.json({
      success: true,
      shop_slug: shopSlug,
      user,
      appointments: Array.isArray(appointments)
        ? appointments
        : [],
      barbers: Array.isArray(barbers)
        ? barbers
        : [],
      services: Array.isArray(services)
        ? services
        : [],
    });
  } catch (error) {
    console.error("Agenda API route failed:", error);

    return NextResponse.json(
      {
        success: false,
        error: "The agenda service is unavailable.",
      },
      {
        status: 500,
      }
    );
  }
}