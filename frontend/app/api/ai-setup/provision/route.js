
import { cookies } from "next/headers";
import { NextResponse } from "next/server";

// Use this deployment's Railway backend; never fall back to another environment.
const API_BASE = (process.env.CHAIRTIME_API_URL || "")
  .trim()
  .replace(/\/+$/, "");

export async function POST() {
  try {
    const cookieStore = await cookies();
    const token = cookieStore.get("chairtime_token")?.value;

    if (!token) {
      return NextResponse.json(
        { detail: "Your login has expired. Please sign in again." },
        { status: 401 }
      );
    }

    if (!API_BASE) {
      return NextResponse.json(
        { detail: "The DayTello backend is not configured." },
        { status: 503 }
      );
    }

    const response = await fetch(
      `${API_BASE}/api/ai-setup/provision`,
      {
        method: "POST",
        headers: {
          Accept: "application/json",
          Authorization: `Bearer ${token}`,
        },
        cache: "no-store",
      }
    );

    const data = await response.json().catch(() => ({
      detail: "The AI Receptionist setup service returned an invalid response.",
    }));

    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error("AI provision proxy error:", error);

    return NextResponse.json(
      { detail: "Could not set up your AI Receptionist." },
      { status: 502 }
    );
  }
}
