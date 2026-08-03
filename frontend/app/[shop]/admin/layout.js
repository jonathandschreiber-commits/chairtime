import { cookies } from "next/headers";
import { redirect } from "next/navigation";

const COOKIE_NAME = "chairtime_token";

const API_URL =
  process.env.CHAIRTIME_API_URL ||
  "https://chairtime-production-94da.up.railway.app";

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
      `${API_URL}/api/auth/me`,
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