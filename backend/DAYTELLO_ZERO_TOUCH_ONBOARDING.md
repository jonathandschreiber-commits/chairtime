# DayTello AI Receptionist: zero-touch voicemail onboarding acceptance contract

Status: **BLOCKED — not production-ready; do not start Test Salon 3 acceptance testing.**
Applies to all new AI Receptionist shops. No per-shop changes in Railway, Vercel, GitHub or HighLevel can be part of customer onboarding.

## Preserve existing working functionality
- AI receptionist takes call; CALL_TRANSFER sends to a dedicated HighLevel voicemail DID, **not directly to the owner's carrier phone**.
- Dedicated DID rings owner's selected number, then HighLevel voicemail after approximately 20 seconds; caller leaves message.
- Signed `InboundMessage` webhook identifies the destination DID and maps to **one** shop.
- Owner SMS includes a secure, expiring playable recording link.
- These steps were live-call tested for Stan's and Bob's Shop; do not alter their phone assignments during development.

## Programmable voice relay development (2026-10-30; offline only)
- The isolated relay now stores signed inbound CallSid -> shop/DID ownership, including the provider AccountSid, so a recording-status callback can be matched even when Twilio omits `To`.
- Completed recording callbacks are persisted once per RecordingSid. A duplicate callback cannot schedule a second owner SMS. A signed, shop-scoped, 24-hour recording link uses a separate Twilio audio proxy rather than treating a Twilio RecordingSid as a HighLevel message ID.
- The owner SMS reuses the existing HighLevel tracked sender and remains gated behind explicit test recipient approval, opt-in, shop/location checks, and test-only feature flags.
- The audio proxy requires a platform-managed Twilio API key SID/secret (`DAYTELLO_VOICE_RELAY_API_KEY_SID`, `DAYTELLO_VOICE_RELAY_API_KEY_SECRET`) and `DAYTELLO_VOICE_RELAY_ACCOUNT_SID`. The webhook uses `DAYTELLO_VOICE_RELAY_AUTH_TOKEN` to verify Twilio signatures. These are platform-wide integration settings, **not per-shop owner configuration**.
- Provider audio is fetched with server-side Basic authentication from the exact Twilio Recordings API endpoint, with redirects disabled, bounded size, content-type checks, and no credentials exposed to owners. If a provider redirect is returned, playback fails closed until a verified redirect handling path is implemented.
- GitHub Actions only validates mocked provider callbacks and responses. No real DID, Twilio account, HighLevel call transfer, SMS delivery, Railway environment, or recording playback has been live-verified.
- A Twilio IncomingPhoneNumbers adapter now performs read-only DID ownership/route verification and supports an exact-number purchase only with BOTH an explicit approval argument and platform test/purchase feature flags. It verifies the assigned webhook after purchase and can recover from a lost purchase response without blindly purchasing twice. Mock-provider tests pass in CI. **A separate service now serializes a test shop's purchase under a PostgreSQL row lock, checks cross-tenant DID conflicts, and stores a disabled, exclusive database claim and owner settings. Neither service is wired to authenticated owner onboarding or live call activation; no real number has been purchased.**\n- Authenticated owner test setup can now select an eligible local voice DID by area code and call the guarded purchase/claim service only after explicit number-purchase confirmation and a platform test flag. Owner number Save can verify the provider's inbound webhook, configure/read back the HighLevel AI-to-DID transfer, and enable the isolated relay assignment only when a separate live-test-call flag is enabled. Both endpoints continue to report customer readiness as false; neither has been deployed or used for a real call.\n- **Owner SMS verification added (offline only):** An authenticated shop owner can request a consent-based six-digit SMS code and confirm possession of a specific number. A durable, tenant-scoped verification record replaces the per-shop environment allowlist when the platform-wide `DAYTELLO_VOICEMAIL_OWNER_VERIFICATION_ENABLED=true` flag is enabled. Codes expire after 10 minutes; requests are throttled; five wrong guesses lock the challenge. The legacy test allowlist remains the default until this is explicitly enabled. This is NOT proof of SMS delivery and does not enable calls or notifications.\n- **Still blocked:** Connect the verification step to the owner-facing onboarding UI, test against actual provider SMS delivery, implement safe owner opt-out/number-change handling and purchase cost ceilings, validate Twilio/HighLevel credentials and API behavior, run an approved real call/voicemail/audio/SMS acceptance test, and implement production-grade monitoring. Do not mark customer-ready. Also finish subscription-to-setup UI integration and purchase cost ceilings, validate Twilio/HighLevel credentials and API behavior, run an approved real call/voicemail/audio/SMS acceptance test, and implement production-grade monitoring. Do not mark customer-ready.

## Existing implementation to reuse
- `app/routes/ai_setup.py`: HighLevel number inventory and purchase, AI agent provisioning, and `daytello_save_staff_transfer` for the AI-to-DID leg.
- `app/voicemail_auto_provision.py`: test-only allocation from pre-reserved DIDs, verified against inventory and tenant claims; **does not buy a DID or configure external forwarding**.
- `app/routes/voicemail_contact_number.py`: authenticated shop-scoped one-number API, SMS controls and read-only readiness check.
- `app/routes/voicemail_webhook.py`, `voicemail_owner_alert.py`, `voicemail_owner_links.py`: signed event intake, owner SMS and recording playback.

## Unresolved provider capability — release blocker
HighLevel public/help documentation covers forwarding to external number, incoming call timeout and voicemail backup **in the Edit Configuration UI**. A supported API route, schema, authentication scope and read-after-write verification for all three settings have not been established.
- Do NOT guess an undocumented API, scrape a private endpoint, or mark configuration successful because the AI transfer action succeeded.
- Obtain documented provider integration or implement a reviewed programmable voice routing architecture with shop-specific DIDs, voicemail capture, signed events and notification behavior.
- Phone purchase can incur charges; test with explicit cost controls and test-only isolation before automating.

## Required provider adapter contract
1. `reserve_or_purchase_did(shop_id)`: idempotent allocation, exclusive database claim, purchase authorization, compensating failure and retry.
2. `configure_forwarding(did, owner_phone, timeout_seconds=20, backup="provider_voicemail")`: validated owner number, loop prevention, provider write and read-after-write verification.
3. `verify_forwarding(did)`: compare exact external destination, timeout and backup, fail closed on missing/ambiguous provider state.
4. `configure_ai_transfer(shop, did)`: uses existing transfer action API and verifies destination.
5. `activate_owner_notifications(shop, owner_phone)`: requires recipient consent, reliable signed events, secure public link and tenant-safe SMS configuration; not a test-only allowlist.
6. `setup_status(shop)`: can indicate ready only after each operation above is proven; partial failure is recoverable and visible in DayTello.
All calls must be idempotent and scoped to the authenticated shop. Do not mutate another tenant's assigned DID or AI agent.

## Acceptance tests
- Completely new Test Salon 3 subscription using test billing, one owner phone number, all setup through DayTello.
- No administrator interventions in HighLevel, Railway, Vercel or GitHub during the test.
- The selected number rings after AI transfer; unanswered call reaches provider voicemail; one SMS arrives with playable recording link.
- Separate shop calls cannot be delivered to another tenant. Duplicate events do not send duplicate SMS.
- Repeat setup and retry failed step; no duplicate DIDs, subscription charges or agents.
- If any provider step is unavailable, show setup incomplete **before** customer calls are advertised as ready.
- Ensure production opt-in/opt-out and monitoring are in place before broad rollout.

## Documentation checked (2026-10-29)
- https://help.gohighlevel.com/support/solutions/articles/155000006881-phone-number-edit-configuration-incoming-calls-settings-
- https://help.gohighlevel.com/support/solutions/articles/48001229976-phone-number-settings-explained

**This document does not assert the missing provider API exists.**
