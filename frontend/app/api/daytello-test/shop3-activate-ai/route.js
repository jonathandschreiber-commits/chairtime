import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { serverApiBase } from "@/lib/server-api-base";

// This is a sandbox-only test gate. No Stripe payment or subscription is
// created, and this endpoint cannot operate on production/other branches.
export async function POST() {
  if (
    process.env.VERCEL_ENV !== "preview" ||
    process.env.VERCEL_GIT_COMMIT_REF !==
      "feature/daytello-highlevel-only-shop3-20261103"
  ) {
    return NextResponse.json({ detail: "Not found" }, { status: 404 });
  }
  const token = (await cookies()).get("chairtime_token")?.value;
  if (!token) {
    return NextResponse.json(
      { detail: "Please sign in to continue." }, { status: 401 }
    );
  }
  try {
    const response = await fetch(
      `${serverApiBase()}/api/auth/test-shop3-activate-ai`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/json",
        },
        cache: "no-store",
      }
    );
    const data = await response.json().catch(() => ({
      detail: "The sandbox setup service returned an invalid response.",
    }));
    return NextResponse.json(data, { status: response.status });
  } catch {
    return NextResponse.json(
      { detail: "Unable to activate isolated Shop #3 setup." },
      { status: 502 }
    );
  }
}
