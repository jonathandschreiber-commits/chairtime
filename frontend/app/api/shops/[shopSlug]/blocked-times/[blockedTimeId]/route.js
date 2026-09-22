import { cookies } from "next/headers";

const API_BASE =
  "https://chairtime-production-94da.up.railway.app";

export async function DELETE(
  request,
  { params }
) {
  try {
    const { shopSlug, blockedTimeId } =
      await params;

    const cookieStore = await cookies();
    const token =
      cookieStore.get("chairtime_token")?.value;

    if (!token) {
      return Response.json(
        { detail: "Not authenticated." },
        { status: 401 }
      );
    }

    const response = await fetch(
      `${API_BASE}/api/admin/blocked-times/${encodeURIComponent(
        blockedTimeId
      )}?shop_slug=${encodeURIComponent(
        shopSlug
      )}`,
      {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        cache: "no-store",
      }
    );

    const text = await response.text();

    return new Response(text, {
      status: response.status,
      headers: {
        "Content-Type":
          response.headers.get("Content-Type") ||
          "application/json",
      },
    });
  } catch (error) {
    console.error(
      "Blocked time proxy DELETE error:",
      error
    );

    return Response.json(
      { detail: "Could not delete blocked time." },
      { status: 500 }
    );
  }
}
