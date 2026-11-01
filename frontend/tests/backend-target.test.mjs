import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  expectedRailwayOrigin,
  requireMatchingBackendOrigin,
  PRODUCTION_RAILWAY_ORIGIN,
  LEGACY_PREVIEW_RAILWAY_ORIGIN,
  STAN_BOB_TEST_RAILWAY_ORIGIN,
  PR5_ONBOARDING_BRANCH,
} from "../lib/backend-target.mjs";

const PR5 = { VERCEL_ENV: "preview", VERCEL_GIT_COMMIT_REF: PR5_ONBOARDING_BRANCH };
const ISOLATED = "https://new-shop-isolated.example.test";

test("PR5 preview requires a separate backend and never accepts production or Stan/Bob", () => {
  assert.throws(() => expectedRailwayOrigin(PR5), /dedicated isolated/);
  for (const forbidden of [
    PRODUCTION_RAILWAY_ORIGIN, LEGACY_PREVIEW_RAILWAY_ORIGIN,
    STAN_BOB_TEST_RAILWAY_ORIGIN,
  ]) {
    assert.throws(
      () => expectedRailwayOrigin({
        ...PR5, DAYTELLO_PR5_ISOLATED_RAILWAY_ORIGIN: forbidden,
      }), /dedicated HTTPS backend/,
    );
  }
  const env = { ...PR5, DAYTELLO_PR5_ISOLATED_RAILWAY_ORIGIN: ISOLATED };
  assert.equal(expectedRailwayOrigin(env), ISOLATED);
  assert.equal(requireMatchingBackendOrigin(ISOLATED, env), ISOLATED);
  assert.throws(() => requireMatchingBackendOrigin(PRODUCTION_RAILWAY_ORIGIN, env),
    /Wrong Railway backend/);
  assert.throws(() => requireMatchingBackendOrigin(STAN_BOB_TEST_RAILWAY_ORIGIN, env),
    /Wrong Railway backend/);
});

test("existing production and Stan/Bob previews retain their original destinations", () => {
  assert.equal(expectedRailwayOrigin({ VERCEL_ENV: "production" }),
    PRODUCTION_RAILWAY_ORIGIN);
  assert.equal(expectedRailwayOrigin({
    VERCEL_ENV: "preview",
    VERCEL_GIT_COMMIT_REF: "feature/daytello-voicemail-owner-sms-20261027",
  }), STAN_BOB_TEST_RAILWAY_ORIGIN);
  assert.equal(expectedRailwayOrigin({
    VERCEL_ENV: "preview", VERCEL_GIT_COMMIT_REF: "another-branch",
  }), LEGACY_PREVIEW_RAILWAY_ORIGIN);
});

test("AI agent provision, status and number purchase all use the same backend proxy", () => {
  const root = fileURLToPath(new URL("../app/api/ai-setup/", import.meta.url));
  for (const path of [
    "provision/route.js", "provision/status/route.js",
    "phone-number/purchase/route.js",
  ]) {
    const code = readFileSync(root + path, "utf8");
    assert.match(code, /serverApiBase\(/, path + " must use shared backend");
    assert.doesNotMatch(code, /process\.env\.CHAIRTIME_API_URL/, path + " bypasses backend pin");
  }
});
