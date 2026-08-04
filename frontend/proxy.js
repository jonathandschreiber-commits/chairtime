import { NextResponse } from "next/server";

const COOKIE_NAME = "chairtime_token";

export function proxy(request) {
  const token = request.cookies.get(COOKIE_NAME)?.value;
  const pathname = request.nextUrl.pathname;

  const isLegacyAdminRoute =
    pathname === "/admin" ||
    pathname.startsWith("/admin/");

  const isShopAdminRoute =
    /^\/[^/]+\/admin(?:\/|$)/.test(pathname);

  const isProtectedAdminRoute =
    isLegacyAdminRoute || isShopAdminRoute;

  if (isProtectedAdminRoute && !token) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);

    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/admin/:path*",
    "/:shop/admin/:path*",
  ],
};