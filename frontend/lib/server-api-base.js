import "server-only";
import { expectedRailwayOrigin } from "./backend-target.mjs";

// All AI setup routes must use this one deployment-scoped origin. A PR #5
// preview without its own isolated backend fails closed before any request.
export function serverApiBase() {
  const raw = (process.env.CHAIRTIME_API_URL || "").trim();
  if (!raw) throw new Error("CHAIRTIME_API_URL must be configured for this deployment.");
  let url;
  try { url = new URL(raw); }
  catch { throw new Error("CHAIRTIME_API_URL is not a valid URL."); }
  if (url.protocol !== "https:" &&
      !(url.protocol === "http:" && ["localhost", "127.0.0.1"].includes(url.hostname))) {
    throw new Error("CHAIRTIME_API_URL must use HTTPS (except local development).");
  }
  if (url.username || url.password || url.search || url.hash || url.pathname !== "/") {
    throw new Error("CHAIRTIME_API_URL must be an origin without credentials or a path.");
  }
  const expected = expectedRailwayOrigin();
  if (expected && url.origin !== expected) {
    throw new Error("Wrong Railway backend configured for this Vercel deployment.");
  }
  const publicRaw = (process.env.NEXT_PUBLIC_API_BASE || "").trim();
  if (publicRaw) {
    let publicUrl;
    try { publicUrl = new URL(publicRaw); }
    catch { throw new Error("NEXT_PUBLIC_API_BASE is not a valid URL."); }
    if (publicUrl.origin !== url.origin || publicUrl.pathname !== "/" ||
        publicUrl.search || publicUrl.hash) {
      throw new Error("Backend URL mismatch between server and browser settings.");
    }
  }
  return url.origin;
}
