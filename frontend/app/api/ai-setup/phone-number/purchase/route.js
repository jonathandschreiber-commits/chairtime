import { cookies } from "next/headers";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "https://chairtime-production-94da.up.railway.app";

export async function POST(request) {
  try {
    const cookieStore = await cookies();
    const token = cookieStore.get("chairtime_token")?.value;

    if (!token) {
      return Response.json(
        {
          detail: "Not authenticated",
        },
        {
          status: 401,
        }
      );
    }

    const body = await request.json();

    const response = await fetch(
      `${BACKEND_URL}/api/ai-setup/phone-number/purchase`,
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

    let data;

    try {
      data = await response.json();
    } catch {
      data = {
        detail:
          "ChairTime received an invalid response from the backend.",
      };
    }

    return Response.json(data, {
      status: response.status,
    });
  } catch (error) {
    console.error(
      "AI phone number purchase proxy error:",
      error
    );

    return Response.json(
      {
        detail:
          "ChairTime could not process the phone number purchase.",
      },
      {
        status: 500,
      }
    );
  }
}
