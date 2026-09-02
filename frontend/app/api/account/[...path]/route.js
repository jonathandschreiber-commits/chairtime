import { NextResponse } from "next/server";
import { cookies } from "next/headers";

function getApiUrl() {
  const apiUrl = process.env.CHAIRTIME_API_URL;

  if (!apiUrl) {
    throw new Error(
      "CHAIRTIME_API_URL environment variable is missing."
    );
  }

  return apiUrl.replace(/\/+$/, "");
}

async function getAuthToken() {
  const cookieStore = await cookies();

  return cookieStore.get("chairtime_token")?.value || "";
}

async function getPath(params) {
  const resolvedParams = await params;
  const pathParts = resolvedParams?.path;

  if (!Array.isArray(pathParts) || pathParts.length === 0) {
    return "";
  }

  return pathParts
    .map((part) => encodeURIComponent(part))
    .join("/");
}

async function proxyAccountRequest(
  request,
  params,
  method
) {
  try {
    const token = await getAuthToken();

    if (!token) {
      return NextResponse.json(
        {
          detail:
            "You must be signed in to manage this account.",
        },
        {
          status: 401,
        }
      );
    }

    const path = await getPath(params);

    if (!path) {
      return NextResponse.json(
        {
          detail: "Account endpoint is missing.",
        },
        {
          status: 400,
        }
      );
    }

    const apiUrl = getApiUrl();

    const incomingUrl = new URL(request.url);

    const backendUrl =
      `${apiUrl}/api/account/${path}` +
      incomingUrl.search;

    const headers = {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
    };

    const fetchOptions = {
      method,
      headers,
      cache: "no-store",
    };

    if (
      method === "POST" ||
      method === "PATCH" ||
      method === "PUT"
    ) {
      const contentType =
        request.headers.get("content-type");

      if (contentType) {
        headers["Content-Type"] = contentType;
      }

      const body = await request.text();

      if (body) {
        fetchOptions.body = body;
      }
    }

    const response = await fetch(
      backendUrl,
      fetchOptions
    );

    const responseText =
      await response.text();

    let data = {};

    if (responseText) {
      try {
        data = JSON.parse(responseText);
      } catch {
        data = {
          detail: responseText,
        };
      }
    }

    return NextResponse.json(
      data,
      {
        status: response.status,
      }
    );
  } catch (error) {
    console.error(
      "Account API proxy error:",
      error
    );

    return NextResponse.json(
      {
        detail:
          "Unable to communicate with the account service.",
      },
      {
        status: 500,
      }
    );
  }
}

export async function GET(
  request,
  { params }
) {
  return proxyAccountRequest(
    request,
    params,
    "GET"
  );
}

export async function POST(
  request,
  { params }
) {
  return proxyAccountRequest(
    request,
    params,
    "POST"
  );
}

export async function PATCH(
  request,
  { params }
) {
  return proxyAccountRequest(
    request,
    params,
    "PATCH"
  );
}

export async function PUT(
  request,
  { params }
) {
  return proxyAccountRequest(
    request,
    params,
    "PUT"
  );
}
