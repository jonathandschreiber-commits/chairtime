import "server-only";

// The browser and server must use the same backend for this deployment.
// These are guards, NOT fallback addresses: a mismatch stops the request.
const EXPECTED_RAILWAY_ORIGIN = {
  production: "https://welcoming-trust-live.up.railway.app",
  preview: "https://chairtime-production-94da.up.railway.app",
};

export function serverApiBase() {
  const raw = (process.env.CHAIRTIME_API_URL || "").trim();
  if (!raw) throw new Error("CHAIRTIME_API_URL must be configured for this deployment.");
  let url;
  try { url = new URL(raw); }
  catch { throw new Error("CHAIRTIME_API_URL is not a valid URL."); }
  if (url.protocol !== "https:" && !(url.protocol === "http:" && ["localhost", "127.0.0.1"].includes(url.hostname))) {
    throw new Error("CHAIRTIME_API_URL must use HTTPS (except local development).");
  }
  if (url.username || url.password || url.search || url.hash || url.pathname !== "/") {
    throw new Error("CHAIRTIME_API_URL must be an origin without credentials or a path.");
  }
  const expected = EXPECTED_RAILWAY_ORIGIN[process.env.VERCEL_ENV];
  if (expected && url.origin !== expected) {
    throw new Error(`Wrong Railway backend configured for Vercel ${process.env.VERCEL_ENV}.`);
  }
  const publicRaw = (process.env.NEXT_PUBLIC_API_BASE || "").trim();
  if (publicRaw) {
    let publicUrl;
    try { publicUrl = new URL(publicRaw); }
    catch { throw new Error("NEXT_PUBLIC_API_BASE is not a valid URL."); }
    if (publicUrl.origin !== url.origin || publicUrl.pathname !== "/" || publicUrl.search || publicUrl.hash) {
      throw new Error("Backend URL mismatch between server and browser settings.");
    }
  }
  return url.origin;
}
