// Keep every step of AI onboarding on the same backend. In particular, PR #5
// must never provision an agent on production or on Stan/Bob's test service.
export const PRODUCTION_RAILWAY_ORIGIN = "https://welcoming-trust-live.up.railway.app";
export const LEGACY_PREVIEW_RAILWAY_ORIGIN = "https://chairtime-production-94da.up.railway.app";
export const STAN_BOB_TEST_RAILWAY_ORIGIN =
  "https://bountiful-manifestation-daytello-voicemail-test.up.railway.app";

export const PR5_ONBOARDING_BRANCH =
  "feature/daytello-general-voicemail-onboarding-20261029";
const OWNER_SMS_BRANCH = "feature/daytello-voicemail-owner-sms-20261027";

export function expectedRailwayOrigin(env = process.env) {
  if (env.VERCEL_ENV === "preview" &&
      env.VERCEL_GIT_COMMIT_REF === PR5_ONBOARDING_BRANCH) {
    // One platform-level setting for the isolated PR #5 preview; no shop
    // owner ever needs to edit Railway or HighLevel during onboarding.
    const raw = (env.DAYTELLO_PR5_ISOLATED_RAILWAY_ORIGIN || "").trim();
    let target;
    try { target = new URL(raw); }
    catch { throw new Error("PR #5 requires a dedicated isolated Railway backend origin."); }
    if (target.protocol !== "https:" || !target.hostname ||
        target.username || target.password || target.port ||
        target.pathname !== "/" || target.search || target.hash ||
        [
          PRODUCTION_RAILWAY_ORIGIN,
          LEGACY_PREVIEW_RAILWAY_ORIGIN,
          STAN_BOB_TEST_RAILWAY_ORIGIN,
        ].includes(target.origin)) {
      throw new Error("PR #5 must use a dedicated HTTPS backend, not production or Stan/Bob.");
    }
    return target.origin;
  }
  if (env.VERCEL_ENV === "preview" &&
      env.VERCEL_GIT_COMMIT_REF === OWNER_SMS_BRANCH) {
    return STAN_BOB_TEST_RAILWAY_ORIGIN;
  }
  return {
    production: PRODUCTION_RAILWAY_ORIGIN,
    preview: LEGACY_PREVIEW_RAILWAY_ORIGIN,
  }[env.VERCEL_ENV];
}
