import { getBackendUrl } from "../../../lib/backend-url.js";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

const COOKIE_NAME = "chairtime_token";

export default async function ShopAdminLayout({
  children,
  params,
}) {
  const { shop } = await params;

  const cookieStore = await cookies();
  const token = cookieStore.get(COOKIE_NAME)?.value;

  if (!token) {
    redirect(
      `/login?next=${encodeURIComponent(
        `/${shop}/admin`
      )}`
    );
  }

  let user = null;

  try {
    const response = await fetch(
      `${getBackendUrl()}/api/auth/me`,
      {
        headers: {
          Accept: "application/json",
          Authorization: `Bearer ${token}`,
        },
        cache: "no-store",
      }
    );

    if (response.ok) {
      user = await response.json();
    }
  } catch (error) {
    console.error(
      "Shop admin authentication failed:",
      error
    );
  }

  if (!user?.shop_slug) {
    redirect("/login");
  }

  if (user.shop_slug !== shop) {
    redirect(`/${user.shop_slug}/admin`);
  }

  return children;
}