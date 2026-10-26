# DayTello voicemail intake — review only

This branch is intentionally NOT deployed or merged.

## What it does
- Receives HighLevel Marketplace `InboundMessage` events at `POST /api/daytello/voicemail`.
- Requires `X-GHL-Signature` (Ed25519); rejects unsigned or tampered requests.
- Processes only `TYPE_VOICEMAIL` events from the configured HighLevel location.
- Routes exclusively by a dedicated `to` telephone number, never caller number/time.
- Stores `(location_id, message_id)` once in `daytello_voicemail_events`.
- Does NOT send any SMS, fetch recordings, or install/publish a HighLevel app.

## Before deployment to the *test* Railway service
1. Review these changes. HighLevel tests with actual signed payloads are still outstanding.
2. Set `HIGHLEVEL_LOCATION_ID` to the intended location, if it is not already configured.
3. Set `DAYTELLO_VOICEMAIL_NUMBER_SHOP_MAP` as a JSON dictionary with **dedicated** voicemail routing numbers mapped to exclusive shop slugs. Example for the existing **test-only** setup:
   `{"+12029725238":"stan-s-shop"}`
4. **Stan's Shop test AI number is +1 202-972-5238.** Dave's Shop test AI number is +1 240-387-5085. Do not map Dave's number to Stan, or share one number between shops. Confirm the real signed webhook `to` value before relying on the map; transfer/forwarding flows may behave differently.
5. Confirm the active Railway service points to `daytello-testing` and deploy only when reviewing the PR is complete.
6. The Marketplace app must be installed/authorized and subscribe to `InboundMessage` using the testing backend HTTPS URL before any events are delivered. The OAuth callback at `/api/daytello/oauth/callback` is implemented on this isolated feature branch, but has **only simulated tests**; do not authorize/install the app until this is deployed to the isolated test backend and live OAuth behavior is reviewed.
7. Leave HighLevel workflow `DayTello - Voicemail Notification TEST` in Draft.

## Limitations / next implementation
- OAuth authorization initiation, callback and encrypted credential storage are implemented, but a real HighLevel OAuth installation and signed webhook have **not** been verified. OAuth is disabled by default.
- Confirm the Marketplace application is installable while in its current Draft configuration before attempting authorization.
- Add owner phone-number consent / opt-out handling, explicit per-shop notification settings, retries, and per-shop delivery logs *after* validating test voicemail payloads.
- Add signed fixture integration tests, a webhook freshness/replay window and operational alerting before enabling production.
- Validate HighLevel's event 'to' number for real two-stage call transfers. Never infer originating shop from same caller/timestamp.
- Privacy: recordings are NOT copied and caller numbers are NOT stored in the current receipt table.

## Relevant documents
- https://marketplace.gohighlevel.com/docs/2023-02-21/webhook/InboundMessage/
- https://marketplace.gohighlevel.com/docs/2021-07-28/webhook/WebhookIntegrationGuide/index.html
