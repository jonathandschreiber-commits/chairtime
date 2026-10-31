"""Explicit, one-shot recovery worker for stranded test voicemail alerts.

This module is intentionally NOT attached to FastAPI startup or any scheduler.
An operator must opt in to a single bounded batch. A future isolated scheduler
can invoke this entrypoint, but merely deploying code never activates SMS.
"""
import argparse
import os
import re


_REQUIRED_FLAGS = (
    "DAYTELLO_VOICE_RELAY_TEST_ONLY",
    "DAYTELLO_VOICEMAIL_TEST_ONLY",
    "DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED",
    "DAYTELLO_VOICE_RELAY_RECOVERY_WORKER_ENABLED",
)


def run_once(*, shop_id=None, limit=25, execute=False):
    """Process at most one bounded batch; return examined, not delivered count.

    The delivery helper atomically claims each queued receipt before any SMS
    provider call. It deliberately never retries an ambiguous send attempt.
    """
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Recovery batch size must be between 1 and 100")
    if execute is not True:
        raise PermissionError("Explicit recovery execution approval required")
    if not isinstance(shop_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", shop_id):
        raise ValueError("An exact shop ID is required for recovery")
    missing = [name for name in _REQUIRED_FLAGS if os.getenv(name) != "true"]
    if missing:
        raise PermissionError(
            "Test-only recovery is disabled: " + ", ".join(missing)
        )

    # Import only after all guards pass; importing the delivery module can
    # initialize database dependencies in the application.
    from app.voice_relay_delivery import recover_queued_relay_alerts
    return recover_queued_relay_alerts(shop_id=shop_id, limit=limit)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run one explicitly authorized, test-only voicemail recovery batch."
    )
    parser.add_argument(
        "--execute", action="store_true",
        help="Required opt-in; may send owner SMS for queued test recordings.",
    )
    parser.add_argument(
        "--shop-id", default=None,
        help="Required exact tenant ID; only this shop's queued receipts are examined.",
    )
    parser.add_argument(
        "--limit", type=int, default=25,
        help="Maximum queued receipts to examine (1-100; default 25).",
    )
    args = parser.parse_args(argv)
    try:
        count = run_once(shop_id=args.shop_id, limit=args.limit, execute=args.execute)
    except (PermissionError, ValueError) as exc:
        parser.exit(2, f"Recovery not started: {exc}\n")
    print(f"Examined {count} queued test voicemail receipt(s) for the selected shop; SMS delivery not confirmed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
