import { cookies } from "next/headers";
import { serverApiBase } from "@/lib/server-api-base";

export async function POST() {
  try {
    const cookieStore = await cookies();
    const token = cookieStore.get("chairtime_token")?.value;
    if (!token) {
      return Response.json({ detail: "Please sign in as the shop owner." }, { status: 401 });
    }
    const response = await fetch(
      `${serverApiBase()}/api/ai-setup/voicemail-onboarding/resume`,
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
      detail: "The voicemail onboarding service returned an invalid response.",
    }));
    return Response.json(data, { status: response.status });
  } catch (error) {
    console.error("Voicemail onboarding resume proxy error:", error);
    return Response.json(
      { detail: "Could not resume the approved voicemail setup." },
      { status: 502 }
    );
  }
}
