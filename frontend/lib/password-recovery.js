import { NextResponse } from "next/server";

export async function passwordRecoveryRequest(request, action) {
  try {
    const body = await request.json();
    const response = await fetch(`${process.env.CHAIRTIME_API_URL}/api/auth/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    const data = await response.json();
    const result = NextResponse.json(
      response.ok
        ? { success: true }
        : { error: typeof data.detail === "string" ? data.detail : "Check the information you entered and try again." },
      { status: response.status, headers: { "Cache-Control": "no-store" } },
    );
    if (response.ok && action === "reset-password") result.cookies.delete("chairtime_token");
    return result;
  } catch {
    return NextResponse.json({ error: "Password reset is temporarily unavailable. Please try again later." },
      { status: 503, headers: { "Cache-Control": "no-store" } });
  }
}
