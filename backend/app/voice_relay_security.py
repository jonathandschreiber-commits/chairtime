"""Twilio-compatible form webhook authentication for the isolated voice relay.

This module does not expose any live HTTP route or authorize shop selection.
Validation MUST precede reading DID, CallSid, DialCallStatus or RecordingSid.
"""
import base64
import hashlib
import hmac
from urllib.parse import urlsplit

def valid_public_https_url(url: str) -> bool:
    """Reject malformed or ambiguous provider callback URLs before signing.

    urlsplit accepts control characters and defers malformed-port errors
    until .port is accessed; fail closed rather than raising an exception.
    """
    if (not isinstance(url, str) or not url or
            any(ord(c) < 33 or ord(c) == 127 or c == "\\" for c in url)):
        return False
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https" and bool(parsed.hostname) and
        parsed.username is None and parsed.password is None and
        not parsed.fragment and (port is None or 1 <= port <= 65535)
    )


def verify_voice_provider_signature(public_url: str, fields: dict[str, str],
                                    provided_signature: str, auth_token: str) -> bool:
    """Verify an x-www-form-urlencoded Twilio request's X-Twilio-Signature.

    The URL must be the exact externally requested HTTPS URL including query
    string. All POST fields must be single-value strings. No JSON, duplicate
    field normalization, proxy URL guessing or partial validation.
    """
    if (not valid_public_https_url(public_url) or
            not isinstance(auth_token, str) or not auth_token or
            not isinstance(provided_signature, str) or not provided_signature or
            not isinstance(fields, dict) or
            not all(isinstance(k, str) and isinstance(v, str)
                    for k, v in fields.items())):
        return False
    signed = public_url + "".join(k + fields[k] for k in sorted(fields))
    digest = hmac.new(auth_token.encode("utf-8"),
                      signed.encode("utf-8"), hashlib.sha1).digest()
    expected = base64.b64encode(digest).decode("ascii")
    return hmac.compare_digest(expected, provided_signature)
