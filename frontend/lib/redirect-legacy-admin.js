import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { getBackendUrl } from "./backend-url.js";

export async function redirectLegacyAdmin(section = "") {
  const token = (await cookies()).get("chairtime_token")?.value;
  const legacyPath = "/admin" + section;
  const loginPath = `/login?next=${encodeURIComponent(legacyPath)}`;
  if (!token) redirect(loginPath);

  let user;
  try {
    const response = await fetch(`${getBackendUrl()}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (response.ok) user = await response.json();
  } catch {
    // Require a verified shop before selecting an admin destination.
  }

  if (!user?.shop_slug) redirect(loginPath);
  redirect(`/${encodeURIComponent(user.shop_slug)}/admin${section}`);
}
