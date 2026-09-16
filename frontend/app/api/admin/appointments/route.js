import { NextResponse } from "next/server";
import { cookies } from "next/headers";

const COOKIE_NAME = "chairtime_token";

async function getBackendConfig() {
  const apiUrl = process.env.CHAIRTIME_API_URL;

  if (!apiUrl) {
    return {
      error: NextResponse.json(
        { detail: "Backend URL is not configured." },
        { status: 500 }
      ),
    };
  }

  const cookieStore = await cookies();
  const token = cookieStore.get(COOKIE_NAME)?.value;

  if (!token) {
    return {
      error: NextResponse.json(
        { detail: "Not authenticated." },
        { status: 401 }
      ),
    };
  }

  return {
    apiUrl,
    token,
  };
}

async function readBackendResponse(response) {
  try {
    return await response.json();
  } catch {
    return {
      detail: "The backend returned an invalid response.",
    };
  }
}

export async function GET() {
  try {
    const config = await getBackendConfig();

    if (config.error) {
      return config.error;
    }

    const response = await fetch(
      `${config.apiUrl}/api/admin/appointments`,
      {
        method: "GET",
        headers: {
          Accept: "application/json",
          Authorization: `Bearer ${config.token}`,
        },
        cache: "no-store",
      }
    );

    const data = await readBackendResponse(response);

    return NextResponse.json(data, {
      status: response.status,
    });
  } catch (error) {
    console.error(
      "Admin appointments GET proxy error:",
      error
    );

    return NextResponse.json(
      {
        detail: "Unable to load appointments.",
      },
      { status: 500 }
    );
  }
}

export async function POST(request) {
  try {
    const config = await getBackendConfig();

    if (config.error) {
      return config.error;
    }

    let body;

    try {
      body = await request.json();
    } catch {
      return NextResponse.json(
        {
          detail: "Invalid appointment information.",
        },
        { status: 400 }
      );
    }

    const response = await fetch(
      `${config.apiUrl}/api/admin/appointments`,
      {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          Authorization: `Bearer ${config.token}`,
        },
        body: JSON.stringify(body),
        cache: "no-store",
      }
    );

    const data = await readBackendResponse(response);

    return NextResponse.json(data, {
      status: response.status,
    });
  } catch (error) {
    console.error(
      "Admin appointments POST proxy error:",
      error
    );

    return NextResponse.json(
      {
        detail: "Unable to create appointment.",
      },
      { status: 500 }
    );
  }
}
