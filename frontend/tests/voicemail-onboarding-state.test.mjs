import test from "node:test";
import assert from "node:assert/strict";
import { isVoicemailConfigurationSaved } from "../lib/voicemail-onboarding-state.mjs";

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
