"""Twilio DID inventory and purchase adapter for the isolated DayTello relay.

This module does not run during onboarding yet. Purchase is opt-in *twice*:
the platform flag and a caller-supplied explicit approval. No provider writes
are made during import, inventory checks, or when either approval is absent.

API contract: https://www.twilio.com/docs/phone-numbers/api/incomingphonenumber-resource
"""
import hashlib
import json
import logging
import os

from app.voice_relay_mode import production_relay_enabled, voice_relay_enabled
import re
from urllib.parse import parse_qsl, urlsplit
from decimal import Decimal, InvalidOperation

import httpx
from fastapi import HTTPException

ACCOUNT_SID = re.compile(r"^AC[a-fA-F0-9]{32}$")
KEY_SID = re.compile(r"^SK[a-fA-F0-9]{32}$")
NUMBER_SID = re.compile(r"^PN[a-fA-F0-9]{32}$")
US_NUMBER = re.compile(r"^\+1[2-9][0-9]{2}[2-9][0-9]{6}$")
BASE = "https://api.twilio.com/2010-04-01/Accounts"
RESERVE_LABEL = "DayTello Relay Reserve"
logger = logging.getLogger(__name__)


def preowned_relay_pool() -> list[str]:
    """Explicit inventory of already-paid, unused relay DIDs; never buys one."""
    raw = os.getenv("DAYTELLO_VOICE_RELAY_PREOWNED_NUMBER_POOL", "").strip()
    if not raw:
        return []
    try:
        numbers = json.loads(raw)
    except (TypeError, ValueError):
        raise HTTPException(503, "Pre-owned relay number pool is invalid")
    if (not isinstance(numbers, list) or len(numbers) > 100
            or any(not isinstance(n, str) or not US_NUMBER.fullmatch(n)
                   for n in numbers)
            or len(set(numbers)) != len(numbers)):
        raise HTTPException(503, "Pre-owned relay number pool is invalid")
    return numbers


def relay_shop_label(shop_id: str) -> str:
    """Deterministic recovery label; never contains customer-provided text."""
    if not isinstance(shop_id, str) or not 1 <= len(shop_id) <= 128:
        raise HTTPException(422, "Invalid shop identity")
    return "DayTello Relay " + hashlib.sha256(shop_id.encode()).hexdigest()[:32]


def relay_inbound_url(origin: str) -> str:
    # Reuse the exact strict origin parser used by signed callback verification.
    from app.routes.voice_relay import _origin
    if origin != _origin():
        raise HTTPException(503, "Voice relay public origin mismatch")
    return origin + "/api/daytello/voice-relay/inbound"


class VoiceRelayNumberProvider:
    """Account-scoped Twilio number adapter; never adopts arbitrary numbers."""

    def __init__(self, client=None):
        self.account_sid = os.getenv("DAYTELLO_VOICE_RELAY_ACCOUNT_SID", "").strip()
        self.key_sid = os.getenv("DAYTELLO_VOICE_RELAY_API_KEY_SID", "").strip()
        self.key_secret = os.getenv("DAYTELLO_VOICE_RELAY_API_KEY_SECRET", "").strip()
        if (not ACCOUNT_SID.fullmatch(self.account_sid)
                or not KEY_SID.fullmatch(self.key_sid) or not self.key_secret):
            raise HTTPException(503, "Voice provider number credentials unavailable")
        self.client = client or httpx.Client(timeout=20, follow_redirects=False)

    def _request(self, method, resource, *, params=None, data=None):
        url = f"{BASE}/{self.account_sid}/{resource}"
        try:
            response = self.client.request(
                method, url, params=params, data=data,
                auth=(self.key_sid, self.key_secret),
                headers={"Accept": "application/json"},
            )
        except httpx.RequestError:
            # A failed POST may already have purchased a number. Never
            # blindly retry a chargeable operation.
            raise HTTPException(503, "Voice provider outcome could not be verified")
        if response.status_code >= 300:
            try:
                error = response.json()
            except ValueError:
                error = None
            code = error.get("code") if isinstance(error, dict) else None
            logger.warning(
                "Twilio relay %s %s returned HTTP %s (Twilio code %s)",
                method, resource, response.status_code,
                code if type(code) is int else "unavailable",
            )
            raise HTTPException(502, "Voice provider number request was not accepted")
        try:
            result = response.json()
        except ValueError:
            raise HTTPException(502, "Voice provider returned invalid number data")
        if not isinstance(result, dict):
            raise HTTPException(502, "Voice provider returned invalid number data")
        return result

    def _list(self, *, label=None, number=None):
        """Read every Twilio inventory page before claiming or buying a DID.

        A single page is not proof that a shop label, reserve, or exact DID
        is absent. Follow only same-account IncomingPhoneNumbers cursors;
        never send a provider write during inventory discovery.
        """
        params = {"PageSize": 100}
        if label is not None:
            params["FriendlyName"] = label
        if number is not None:
            params["PhoneNumber"] = number
        records = []
        seen_cursors = set()
        expected_path = (
            f"/2010-04-01/Accounts/{self.account_sid}/IncomingPhoneNumbers.json"
        )
        for _ in range(100):
            payload = self._request("GET", "IncomingPhoneNumbers.json", params=params)
            page = payload.get("incoming_phone_numbers")
            if not isinstance(page, list) or any(not isinstance(r, dict) for r in page):
                raise HTTPException(502, "Voice provider returned invalid number data")
            records.extend(page)
            cursor = payload.get("next_page_uri")
            if cursor is None:
                return records
            if not isinstance(cursor, str) or not cursor or cursor in seen_cursors:
                raise HTTPException(409, "Voice number inventory is incomplete")
            seen_cursors.add(cursor)
            parsed = urlsplit(cursor)
            if (parsed.scheme or parsed.netloc or parsed.fragment
                    or parsed.path != expected_path or not parsed.query):
                raise HTTPException(409, "Voice number inventory is incomplete")
            pairs = parse_qsl(parsed.query, keep_blank_values=True)
            if (not pairs or len({key for key, _ in pairs}) != len(pairs)
                    or not any(key in {"Page", "PageToken"} for key, _ in pairs)):
                raise HTTPException(409, "Voice number inventory is incomplete")
            params = dict(pairs)
            # Twilio cursors may omit the original filters. Preserve them
            # across every page, and reject a cursor that changes scope.
            if label is not None:
                if ("FriendlyName" in params
                        and params["FriendlyName"] != label):
                    raise HTTPException(409, "Voice number inventory is incomplete")
                params["FriendlyName"] = label
            if number is not None:
                if ("PhoneNumber" in params
                        and params["PhoneNumber"] != number):
                    raise HTTPException(409, "Voice number inventory is incomplete")
                params["PhoneNumber"] = number
        raise HTTPException(409, "Voice number inventory is incomplete")

    def _matches(self, shop_id):
        label = relay_shop_label(shop_id)
        matches = [r for r in self._list(label=label)
                   if r.get("friendly_name") == label]
        if len(matches) > 1:
            raise HTTPException(409, "Multiple relay numbers match this shop")
        return matches

    def list_reserved_relay_numbers(self):
        """Discover already-owned, explicitly labeled relay DIDs via GET only.

        New shops can use a provider-owned reserve without a per-number
        Railway environment edit. Exact ownership and webhook configuration
        are independently rechecked before a database assignment.
        """
        records = self._list(label=RESERVE_LABEL)
        numbers = [
            r.get("phone_number") for r in records
            if r.get("friendly_name") == RESERVE_LABEL
            and isinstance(r.get("phone_number"), str)
            and US_NUMBER.fullmatch(r["phone_number"])
        ]
        if len(numbers) != len(set(numbers)):
            raise HTTPException(409, "Reserved relay inventory has duplicate numbers")
        return sorted(numbers)

    def verify_route(self, record, shop_id, expected_number=None, *, reserved=False):
        """Fail closed on a changed route, account, DID, or phone ownership."""
        expected_url = relay_inbound_url(
            os.getenv("DAYTELLO_VOICE_RELAY_PUBLIC_ORIGIN", "").rstrip("/"))
        number = record.get("phone_number")
        if (record.get("account_sid") != self.account_sid
                or record.get("friendly_name") != (RESERVE_LABEL if reserved else relay_shop_label(shop_id))
                or not isinstance(number, str) or not US_NUMBER.fullmatch(number)
                or (expected_number is not None and number != expected_number)
                or not NUMBER_SID.fullmatch(str(record.get("sid") or ""))
                or record.get("voice_url") != expected_url
                or record.get("voice_method") != "POST"
                or record.get("voice_application_sid")
                or record.get("trunk_sid")
                or not isinstance(record.get("capabilities"), dict)
                or record["capabilities"].get("voice") is not True
                or record.get("status") != "in-use"):
            raise HTTPException(409, "Voice relay number route is not verified")
        return {"number": number, "provider_sid": record["sid"],
                "route_verified": True}

    def find_existing(self, shop_id, *, expected_number=None):
        matches = self._matches(shop_id)
        if not matches:
            # A reserved provider-owned DID can be adopted by exact number
            # even without a static pool setting. The provider must label it
            # DayTello Relay Reserve and retain the verified inbound webhook.
            # Never infer a shop claim from an arbitrary provider-owned DID.
            preowned_relay_pool()  # Reject invalid legacy pool configuration.
            if expected_number is None or not US_NUMBER.fullmatch(expected_number):
                return None
            exact = [r for r in self._list(number=expected_number)
                     if r.get("phone_number") == expected_number]
            if not exact:
                return None
            if len(exact) != 1:
                raise HTTPException(409, "Reserved relay number ownership is ambiguous")
            return self.verify_route(
                exact[0], shop_id, expected_number, reserved=True)
        # Re-read the exact DID: a stale friendly-name search cannot prove
        # its current inbound webhook or that the number still belongs here.
        number = matches[0].get("phone_number")
        if not isinstance(number, str) or not US_NUMBER.fullmatch(number):
            raise HTTPException(409, "Invalid provider-owned relay number")
        exact = [r for r in self._list(number=number)
                 if r.get("phone_number") == number]
        if len(exact) != 1:
            raise HTTPException(409, "Voice relay number ownership is ambiguous")
        # The friendly-name lookup and exact-number readback must refer to
        # the same provider resource. A reassigned DID between requests must
        # not be adopted even if its webhook and friendly name appear valid.
        if (exact[0].get("sid") != matches[0].get("sid")
                or exact[0].get("account_sid") != matches[0].get("account_sid")):
            raise HTTPException(409, "Voice relay number ownership changed during verification")
        return self.verify_route(exact[0], shop_id, expected_number)

    def find_available_voice_number(self, area_code=None):
        """Choose one voice-capable US DID without making a purchase.

        Twilio availability is a snapshot, not a reservation. The caller must
        still obtain explicit purchase approval and handle a sold-out result.
        """
        if area_code is not None and (not isinstance(area_code, str)
                or not re.fullmatch(r"[2-9][0-9]{2}", area_code)):
            raise HTTPException(422, "Invalid US area code")
        params = {"VoiceEnabled": "true", "PageSize": 20}
        if area_code is not None:
            params["AreaCode"] = area_code
        payload = self._request("GET", "AvailablePhoneNumbers/US/Local.json", params=params)
        records = payload.get("available_phone_numbers")
        if not isinstance(records, list):
            raise HTTPException(502, "Voice number availability was not verified")
        candidates = sorted({
            r["phone_number"] for r in records
            if (isinstance(r, dict)
                and isinstance(r.get("phone_number"), str)
                and US_NUMBER.fullmatch(r["phone_number"])
                and (area_code is None or r["phone_number"][2:5] == area_code)
                and isinstance(r.get("capabilities"), dict)
                and r["capabilities"].get("voice") is True
                and r.get("address_requirements") == "none")
        })
        if not candidates:
            raise HTTPException(409, "No eligible local voice numbers found")
        return candidates[0]

    def verify_exact_local_number_available(self, phone_number):
        """Prove the exact DID is an available US *local* number.

        An E.164 prefix alone cannot establish a number's Twilio type.
        Without this check a toll-free or other DID could be purchased
        against the cheaper local-number price ceiling.
        """
        payload = self._request(
            "GET", "AvailablePhoneNumbers/US/Local.json",
            params={"Contains": phone_number, "VoiceEnabled": "true",
                    "PageSize": 20},
        )
        records = payload.get("available_phone_numbers")
        if not isinstance(records, list) or payload.get("next_page_uri"):
            raise HTTPException(409, "Exact local relay number availability is unverified")
        matches = [r for r in records if (
            isinstance(r, dict) and r.get("phone_number") == phone_number
            and isinstance(r.get("capabilities"), dict)
            and r["capabilities"].get("voice") is True
            and r.get("address_requirements") == "none"
        )]
        if len(matches) != 1:
            raise HTTPException(409, "Exact local relay number availability is unverified")

    def verify_monthly_number_cost(self):
        """Fail closed unless live account pricing fits the operator's USD cap.

        This checks the recurring *local DID* fee only. Voice minutes,
        recording, messaging, taxes and any other fees are separate.
        """
        raw_cap = os.getenv("DAYTELLO_VOICE_RELAY_MAX_MONTHLY_USD", "").strip()
        try:
            cap = Decimal(raw_cap)
        except (InvalidOperation, ValueError):
            raise HTTPException(503, "Voice relay monthly cost ceiling unavailable")
        if not cap.is_finite() or cap <= 0:
            raise HTTPException(503, "Voice relay monthly cost ceiling unavailable")
        pricing_sid = os.getenv("DAYTELLO_VOICE_RELAY_PRICING_KEY_SID", "").strip()
        pricing_secret = os.getenv("DAYTELLO_VOICE_RELAY_PRICING_KEY_SECRET", "").strip()
        if pricing_sid or pricing_secret:
            if not KEY_SID.fullmatch(pricing_sid) or not pricing_secret:
                raise HTTPException(503, "Voice provider pricing credentials incomplete")
            pricing_auth = (pricing_sid, pricing_secret)
        else:
            pricing_auth = (self.key_sid, self.key_secret)
        try:
            response = self.client.request(
                "GET", "https://pricing.twilio.com/v1/PhoneNumbers/Countries/US",
                auth=pricing_auth,
                headers={"Accept": "application/json"},
            )
        except httpx.RequestError:
            raise HTTPException(503, "Voice provider pricing could not be verified")
        if response.status_code != 200:
            logger.warning("Twilio US phone-number pricing returned HTTP %s", response.status_code)
            raise HTTPException(502, "Voice provider pricing could not be verified")
        try:
            payload = response.json()
        except ValueError:
            logger.warning("Twilio US phone-number pricing returned invalid JSON")
            raise HTTPException(502, "Voice provider pricing could not be verified")
        if (not isinstance(payload, dict)
                or payload.get("iso_country") != "US"
                or payload.get("price_unit") != "USD"
                or not isinstance(payload.get("phone_number_prices"), list)):
            raise HTTPException(409, "Voice provider local number price is unavailable")
        local = [item for item in payload["phone_number_prices"]
                 if isinstance(item, dict) and item.get("number_type") == "local"]
        if len(local) != 1:
            raise HTTPException(409, "Voice provider local number price is unavailable")
        try:
            current = Decimal(str(local[0]["current_price"]))
            base = Decimal(str(local[0]["base_price"]))
        except (KeyError, InvalidOperation, ValueError):
            raise HTTPException(409, "Voice provider local number price is unavailable")
        if (not current.is_finite() or not base.is_finite()
                or current <= 0 or base <= 0):
            raise HTTPException(409, "Voice provider local number price is unavailable")
        if max(current, base) > cap:
            raise HTTPException(409, "Voice relay monthly number cost exceeds approved ceiling")

    def purchase_approved_number(self, shop_id, phone_number, *, approved=False):
        """Purchase *one exact* DID only after explicit cost authorization.

        The caller must serialize provisioning per shop and persist the
        returned number as an exclusive disabled database assignment before
        enabling calls. Never invoke from a public customer route as-is.
        """
        relay_shop_label(shop_id)
        if not isinstance(phone_number, str) or not US_NUMBER.fullmatch(phone_number):
            raise HTTPException(422, "A valid exact US relay number is required")
        existing = self.find_existing(shop_id, expected_number=phone_number)
        if existing:
            if existing["number"] != phone_number:
                raise HTTPException(409, "This shop already owns a different relay number")
            return existing
        if (approved is not True or
                os.getenv("DAYTELLO_VOICE_RELAY_PURCHASE_ENABLED") != "true" or
                not voice_relay_enabled()):
            raise HTTPException(409, "Voice relay purchase is not authorized")
        # A DID already in the account must not be repurposed. It may be
        # serving another shop, even if its friendly name is unfamiliar.
        if any(r.get("phone_number") == phone_number
               for r in self._list(number=phone_number)):
            raise HTTPException(409, "This phone number is already in use")
        self.verify_exact_local_number_available(phone_number)
        # Confirm account-specific monthly DID price before any chargeable POST.
        # Other usage charges remain outside this ceiling.
        self.verify_monthly_number_cost()
        url = relay_inbound_url(
            os.getenv("DAYTELLO_VOICE_RELAY_PUBLIC_ORIGIN", "").rstrip("/"))
        try:
            self._request("POST", "IncomingPhoneNumbers.json", data={
                "PhoneNumber": phone_number,
                "FriendlyName": relay_shop_label(shop_id),
                "VoiceUrl": url,
                "VoiceMethod": "POST",
            })
        except HTTPException as exc:
            # A network timeout after a chargeable POST is ambiguous.
            # Recover only when the provider confirms the exact shop/DID.
            if exc.status_code != 503:
                raise
            recovered = self.find_existing(shop_id, expected_number=phone_number)
            if recovered:
                return recovered
            raise HTTPException(409, "Phone purchase outcome requires reconciliation")
        verified = self.find_existing(shop_id, expected_number=phone_number)
        if not verified:
            raise HTTPException(409, "Purchased relay number was not verified")
        return verified

    def find_verified_reserve(self, number):
        records = [r for r in self._list(number=number) if r.get("phone_number") == number]
        if not records:
            return None
        if len(records) != 1:
            raise HTTPException(409, "Reserved relay number ownership is ambiguous")
        return self.verify_route(records[0], None, number, reserved=True)

    def prepare_reserve_purchase(self):
        number = self.find_available_voice_number()
        self.verify_exact_local_number_available(number)
        self.verify_monthly_number_cost()
        return number

    def purchase_reserve(self, number):
        if (os.getenv("DAYTELLO_VOICE_RELAY_PURCHASE_ENABLED") != "true"
                or not production_relay_enabled()):
            raise HTTPException(409, "Production reserve purchasing is disabled")
        url = relay_inbound_url(
            os.getenv("DAYTELLO_VOICE_RELAY_PUBLIC_ORIGIN", "").rstrip("/"))
        self._request("POST", "IncomingPhoneNumbers.json", data={
            "PhoneNumber": number,
            "FriendlyName": RESERVE_LABEL,
            "VoiceUrl": url,
            "VoiceMethod": "POST",
        })
        if not self.find_verified_reserve(number):
            raise HTTPException(503, "Purchased production relay was not verified")
