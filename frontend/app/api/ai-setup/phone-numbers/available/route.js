import { NextResponse } from "next/server";
import { cookies } from "next/headers";

const API_BASE =
  "https://chairtime-production-94da.up.railway.app";

export async function GET(request) {
  const cookieStore = await cookies();
  const token =
    cookieStore.get("chairtime_token")?.value;

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

  const { searchParams } = new URL(request.url);

  const areaCode = String(
    searchParams.get("area_code") || ""
  ).replace(/\D/g, "");

  if (areaCode.length !== 3) {
    return NextResponse.json(
      {
        error:
          "Enter a valid 3-digit U.S. area code.",
      },
      {
        status: 400,
      }
    );
  }

  const response = await fetch(
    `${API_BASE}/api/ai-setup/phone-numbers/available?area_code=${encodeURIComponent(
      areaCode
    )}`,
    {
      method: "GET",

      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
      },

      cache: "no-store",
    }
  );

  const data = await response
    .json()
    .catch(() => ({}));

  return NextResponse.json(data, {
    status: response.status,
  });
}
