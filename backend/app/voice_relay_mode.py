import os


def production_relay_enabled():
    return (
        os.getenv("DAYTELLO_VOICE_RELAY_PRODUCTION_ENABLED") == "true"
        and os.getenv("DAYTELLO_VOICE_RELAY_TEST_ONLY") != "true"
        and os.getenv("DAYTELLO_VOICEMAIL_TEST_ONLY") != "true"
        and os.getenv("DAYTELLO_VOICEMAIL_OWNER_VERIFICATION_ENABLED") == "true"
    )

def voice_relay_enabled():
    if os.getenv("DAYTELLO_VOICE_RELAY_PRODUCTION_ENABLED") == "true":
        return production_relay_enabled()
    return os.getenv("DAYTELLO_VOICE_RELAY_TEST_ONLY") == "true"
