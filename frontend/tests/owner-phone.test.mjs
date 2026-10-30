import test from "node:test";
import assert from "node:assert/strict";
import { isValidUsOwnerPhone, normalizeUsOwnerPhone } from "../lib/owner-phone.mjs";

test("normalizes valid US owner numbers without changing destination", () => {
  for (const input of ["2025550199", "(202) 555-0199", "+1 202 555 0199", "+12025550199"]) {
    assert.equal(normalizeUsOwnerPhone(input), "+12025550199");
  }
  assert.equal(isValidUsOwnerPhone("+12025550199"), true);
});

test("rejects invalid NANP numbers, extensions, and malformed input", () => {
  for (const input of [
    "", "123", "+1202555019", "+120255501990", "+10125550199",
    "++12025550199", "202+5550199",
    "+12021550199", "+12025550199x2", "+12025550199 ext 2",
    "\\+12025550199", "2025550199;DROP", "+442071234567",
    null, {}, 2025550199,
  ]) {
    assert.equal(normalizeUsOwnerPhone(input), null, String(input));
  }
});

test("verification API requires exact +1 E.164 destination", () => {
  for (const input of ["2025550199", "  +12025550199", "+12025550199 ", "+442071234567", "\\+12025550199"]) {
    assert.equal(isValidUsOwnerPhone(input), false, input);
  }
});
