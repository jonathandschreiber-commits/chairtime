"""Provider-neutral programmable voice relay response builders.

Not connected to live routing. Responses are deliberately pure and do not
manage Twilio accounts, phone numbers, callbacks or SMS themselves.
"""
import re
from app.voice_relay_security import valid_public_https_url
from xml.etree import ElementTree as ET

E164_US = re.compile(r"^\+1[2-9][0-9]{2}[2-9][0-9]{6}$")


def _https_url(url: str) -> str:
    if not valid_public_https_url(url):
        raise ValueError("A public HTTPS callback URL is required")
    return url


def _response(child):
    root = ET.Element("Response")
    root.append(child)
    return ET.tostring(root, encoding="unicode")


def forward_to_employee(phone: str, dial_complete_url: str, timeout: int = 5,
                        owner_screen_url: str | None = None) -> str:
    """Dial employee, then hand control back via signed provider callback.

    Twilio's Dial has an approximately 5-second additional buffer, therefore
    5 here corresponds to roughly 10 seconds of ringing (about two rings).
    A short ring window helps the DayTello voicemail prompt answer before the
    owner's carrier voicemail intercepts the transferred call.
    Never pass the owner number in an inbound request: it must come from the
    authenticated shop's stored settings after DID-based tenant resolution.
    """
    if not E164_US.fullmatch(phone):
        raise ValueError("Invalid employee phone number")
    if timeout < 5 or timeout > 30:
        raise ValueError("Unsupported employee ringing timeout")
    dial = ET.Element("Dial", {
        "timeout": str(timeout),
        "action": _https_url(dial_complete_url),
        "method": "POST",
        "answerOnBridge": "true",
    })
    number_attributes = ({"url": _https_url(owner_screen_url), "method": "POST"}
                         if owner_screen_url else {})
    ET.SubElement(dial, "Number", number_attributes).text = phone
    return _response(dial)


def screen_owner_call(confirm_url: str) -> str:
    """Require a human to press 1 before bridging a transferred call.

    A carrier voicemail may answer an owner's phone before the short Dial
    timeout. Without confirmation it would count as an answered call and
    swallow DayTello's voicemail fallback.
    """
    root = ET.Element("Response")
    gather = ET.SubElement(root, "Gather", {
        "input": "dtmf", "numDigits": "1", "timeout": "5",
        "action": _https_url(confirm_url), "method": "POST",
    })
    ET.SubElement(gather, "Say").text = (
        "DayTello call transfer. Press 1 to speak with the caller."
    )
    ET.SubElement(root, "Hangup")
    return ET.tostring(root, encoding="unicode")


def owner_screen_result(digits: str | None) -> str:
    """Only an explicit keypress bridges; silence/voicemail hangs up."""
    if digits == "1":
        return "<Response><Say>Connecting you now.</Say></Response>"
    return completed_recording()


def voicemail_after_unanswered(recording_complete_url: str,
                               recording_ready_url: str) -> str:
    """Prompt caller and record; completed recording uses a separate callback.

    Caller/recording callbacks must independently verify provider signatures,
    call SID and assigned DID before they can create a shop-scoped SMS.
    """
    root = ET.Element("Response")
    ET.SubElement(root, "Say").text = "We could not reach anyone. Please leave a message after the tone."
    ET.SubElement(root, "Record", {
        "action": _https_url(recording_complete_url),
        "method": "POST",
        "maxLength": "120",
        "timeout": "5",
        "playBeep": "true",
        "recordingStatusCallback": _https_url(recording_ready_url),
        "recordingStatusCallbackMethod": "POST",
        "recordingStatusCallbackEvent": "completed",
    })
    ET.SubElement(root, "Hangup")
    return ET.tostring(root, encoding="unicode")


def completed_recording() -> str:
    return "<Response><Hangup /></Response>"


def after_employee_dial(dial_call_status: str, recording_complete_url: str,
                        recording_ready_url: str, dial_bridged: str | None = None) -> str:
    """Only unanswered or failed employee calls go to voicemail.

    Twilio DialCallStatus "completed" means the employee leg connected.
    Never record a voicemail after an answered conversation, or on an
    unexpected/missing status. The signed callback route must independently
    authenticate the provider request and verify shop/DID ownership.
    """
    normalized = str(dial_call_status or "").strip().lower()
    # "canceled" means the dial attempt was explicitly terminated before
    # answer (for example via the provider API), not a ringing timeout.
    # Never turn an intentionally canceled transfer into a voicemail prompt.
    if normalized == "canceled":
        return completed_recording()
    # Carrier voicemail may answer without ever bridging to the caller.
    if normalized == "completed" and str(dial_bridged).lower() != "false":
        return completed_recording()
    if normalized in {"no-answer", "busy", "failed"} or (
            normalized == "completed" and str(dial_bridged).lower() == "false"):
        return voicemail_after_unanswered(
            recording_complete_url, recording_ready_url
        )
    raise ValueError("Unrecognized dial completion status")
