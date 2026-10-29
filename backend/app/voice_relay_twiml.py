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


def forward_to_employee(phone: str, dial_complete_url: str, timeout: int = 15) -> str:
    """Dial employee, then hand control back via signed provider callback.

    Twilio's Dial has an approximately 5-second additional buffer, therefore
    15 here corresponds to roughly 20 seconds of ringing.
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
    ET.SubElement(dial, "Number").text = phone
    return _response(dial)


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
                        recording_ready_url: str) -> str:
    """Only unanswered or failed employee calls go to voicemail.

    Twilio DialCallStatus "completed" means the employee leg connected.
    Never record a voicemail after an answered conversation, or on an
    unexpected/missing status. The signed callback route must independently
    authenticate the provider request and verify shop/DID ownership.
    """
    normalized = str(dial_call_status or "").strip().lower()
    if normalized == "completed":
        return completed_recording()
    if normalized in {"no-answer", "busy", "failed", "canceled"}:
        return voicemail_after_unanswered(
            recording_complete_url, recording_ready_url
        )
    raise ValueError("Unrecognized dial completion status")
