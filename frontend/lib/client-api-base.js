// Browser requests use only the configured public backend for this deployment.
// The environment value is compiled into the frontend by Next.js.
export function clientApiBase() {
  const raw = (process.env.NEXT_PUBLIC_API_BASE || "").trim();
  if (!raw) throw new Error("NEXT_PUBLIC_API_BASE must be configured for this deployment.");
  let url;
  try { url = new URL(raw); }
  catch { throw new Error("NEXT_PUBLIC_API_BASE is not a valid URL."); }
  if (url.protocol !== "https:" && !(url.protocol === "http:" && ["localhost", "127.0.0.1"].includes(url.hostname))) {
    throw new Error("NEXT_PUBLIC_API_BASE must use HTTPS (except local development).");
  }
  if (url.username || url.password || url.search || url.hash || url.pathname !== "/") {
    throw new Error("NEXT_PUBLIC_API_BASE must be an origin without credentials or a path.");
  }
  return url.origin;
}
