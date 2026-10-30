"""Verified programmable-voice recording references.

A Twilio RecordingSid is not a HighLevel message ID. Never feed one into
HighLevel's recording proxy or issue an owner SMS before an authenticated
recording retrieval implementation exists.
"""
import re
from urllib.parse import urlsplit

from fastapi import HTTPException

_RECORDING = re.compile(r"^RE[a-fA-F0-9]{32}$")
_ACCOUNT = re.compile(r"^AC[a-fA-F0-9]{32}$")


def verified_recording_reference(fields: dict, configured_account_sid: str) -> tuple[str, str]:
    """Validate the provider account and recording identity after signature verification.

    Must only be called after the webhook signature, CallSid and exclusive
    relay DID assignment have been verified by the route.
    """
    account = fields.get("AccountSid")
    recording = fields.get("RecordingSid")
    if not _ACCOUNT.fullmatch(configured_account_sid or ""):
        raise HTTPException(503, "Voice recording account is not configured")
    if account != configured_account_sid or not _ACCOUNT.fullmatch(account or ""):
        raise HTTPException(403, "Voice recording account mismatch")
    if not _RECORDING.fullmatch(recording or ""):
        raise HTTPException(422, "Invalid recording identifier")
    return account, recording


def verified_recording_url(url: str, account_sid: str, recording_sid: str) -> str:
    """Allow only the exact provider recording resource, never arbitrary URLs.

    The eventual audio proxy must authenticate with the provider server-side,
    enforce content/size limits, and never expose provider credentials.
    """
    try:
        parsed = urlsplit(url)
    except (TypeError, ValueError):
        raise HTTPException(422, "Invalid recording resource")
    expected = (
        f"/2010-04-01/Accounts/{account_sid}/Recordings/{recording_sid}"
    )
    if (parsed.scheme != "https" or parsed.hostname != "api.twilio.com"
            or parsed.port not in (None, 443) or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment
            or parsed.path not in (expected, expected + ".json")):
        raise HTTPException(422, "Invalid recording resource")
    return url
