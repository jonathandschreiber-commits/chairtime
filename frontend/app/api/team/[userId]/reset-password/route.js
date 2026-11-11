import { getBackendUrl } from "../../../../../lib/backend-url.js";
import { NextResponse } from "next/server";
import { cookies } from "next/headers";


export async function POST(
  request,
  { params }
) {
  try {
    const cookieStore =
      await cookies();

    const token =
      cookieStore.get(
        "chairtime_token"
      )?.value;

    if (!token) {
      return NextResponse.json(
        {
          error:
            "Authentication required.",
        },
        {
          status: 401,
        }
      );
    }

    const resolvedParams =
      await params;

    const userId =
      resolvedParams.userId;

    if (!userId) {
      return NextResponse.json(
        {
          error:
            "Team member is required.",
        },
        {
          status: 400,
        }
      );
    }

    const body =
      await request.json();

    const response =
      await fetch(
        `${getBackendUrl()}/api/team/${encodeURIComponent(
          userId
        )}/reset-password`,
        {
          method: "POST",

          headers: {
            Authorization:
              `Bearer ${token}`,

            "Content-Type":
              "application/json",

            Accept:
              "application/json",
          },

          body:
            JSON.stringify(body),

          cache: "no-store",
        }
      );

    const data =
      await response.json();

    return NextResponse.json(
      data,
      {
        status:
          response.status,
      }
    );
  } catch (error) {
    console.error(
      "Team password reset proxy error:",
      error
    );

    return NextResponse.json(
      {
        error:
          "The password could not be reset.",
      },
      {
        status: 500,
      }
    );
  }
}
