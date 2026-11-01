import test from "node:test";
import assert from "node:assert/strict";
import { isVoicemailConfigurationSaved, voicemailSetupRefreshKey } from "../lib/voicemail-onboarding-state.mjs";

test("a saved, activated relay advances configuration review without claiming live readiness", () => {
  const state = {
    configuration_complete: true, phone_number: "+12025550199",
    setup_complete: false, ready: false, live_call_test_required: true,
  };
  assert.equal(isVoicemailConfigurationSaved(state), true);
  assert.equal(state.ready, false);
  assert.equal(state.setup_complete, false);
});

test("SMS alone, pending owner approval, or invalid phone cannot advance", () => {
  assert.equal(isVoicemailConfigurationSaved({
    sms_ready: true, configuration_complete: false,
    phone_number: "+12025550199",
  }), false);
  assert.equal(isVoicemailConfigurationSaved({
    configuration_complete: true, phone_number: "bad",
  }), false);
  assert.equal(isVoicemailConfigurationSaved({ configuration_complete: true }), false);
  assert.equal(isVoicemailConfigurationSaved(null), false);
});

test("resuming a saved owner transfer reloads the unified setup for the same shop", () => {
  const pending = voicemailSetupRefreshKey("new-shop", "+12405550124", false);
  const activated = voicemailSetupRefreshKey("new-shop", "+12405550124", true);
  assert.notEqual(pending, activated);
  assert.equal(activated, voicemailSetupRefreshKey("new-shop", "+12405550124", true));
  assert.notEqual(activated, voicemailSetupRefreshKey("other-shop", "+12405550124", true));
  assert.notEqual(activated, voicemailSetupRefreshKey("new-shop", "+12405550126", true));
});
