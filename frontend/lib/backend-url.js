export function getBackendUrl() {
  const url = process.env.CHAIRTIME_API_URL?.trim().replace(/\/+$/, "");
  if (!url) throw new Error("Backend URL is not configured.");
  return url;
}
