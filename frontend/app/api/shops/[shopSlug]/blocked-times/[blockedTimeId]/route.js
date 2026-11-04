import { serverApiBase } from "@/lib/server-api-base";
import { cookies } from "next/headers";



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
      `${serverApiBase()}/api/admin/blocked-times/${encodeURIComponent(
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
