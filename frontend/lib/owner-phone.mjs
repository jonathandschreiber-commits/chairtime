// Shared by the preview-only owner verification API and its UI.
// This checks syntax only; possession, consent and routing safety are
// enforced separately by the authenticated backend.
const E164_US = /^\+1[2-9][0-9]{2}[2-9][0-9]{6}$/;

export function normalizeUsOwnerPhone(value) {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  // Reject letters, extensions and other unexpected characters rather than
  // silently stripping them into a different destination.
  if (!/^[+()\- .0-9]+$/.test(trimmed)) return null;
  const digits = trimmed.replace(/\D/g, "");
  const normalized = digits.length === 10 ? "+1" + digits
    : digits.length === 11 && digits.startsWith("1") ? "+" + digits
    : null;
  return normalized && E164_US.test(normalized) ? normalized : null;
}

export function isValidUsOwnerPhone(value) {
  return typeof value === "string" && E164_US.test(value);
}
