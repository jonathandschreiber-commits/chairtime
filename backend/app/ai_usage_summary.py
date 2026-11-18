"""Read-only billing view. Stripe's invoice preview is the billing source of truth."""
from datetime import datetime, timezone
from decimal import Decimal


def value(obj, key, default=None):
    return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)


def object_id(obj):
    return obj if isinstance(obj, str) else value(obj, "id")


def iso(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat() if timestamp else None


def summarize(subscription, preview, usage_price=None):
    items = value(value(subscription, "items", {}), "data", [])
    if value(value(subscription, "items", {}), "has_more", False):
        raise ValueError("Incomplete subscription items")
    metered = [i for i in items if value(value(value(i, "price", {}), "recurring", {}), "usage_type") == "metered"]
    status = value(subscription, "status")
    fixed = 0
    for item in items:
        price = value(item, "price", {})
        recurring = value(price, "recurring", {})
        if value(recurring, "usage_type") == "metered":
            continue
        if value(recurring, "interval") != "month" or value(recurring, "interval_count", 1) != 1 or value(price, "unit_amount") is None:
            fixed = None
            break
        fixed += value(price, "unit_amount") * (value(item, "quantity", 1) or 0)
    first = metered[0] if len(metered) == 1 else (items[0] if items else {})
    start = value(first, "current_period_start", value(subscription, "current_period_start"))
    end = value(first, "current_period_end", value(subscription, "current_period_end"))
    result = {
        "status": status, "currency": value(subscription, "currency", "usd"),
        "period_start": iso(start), "period_end": iso(end),
        "trial_end": iso(value(subscription, "trial_end")),
        "cancel_at": iso(value(subscription, "cancel_at")),
        "cancel_at_period_end": bool(value(subscription, "cancel_at_period_end", False)),
        "monthly_base_cents": fixed,
        "metered": bool(metered), "usage_available": False,
        "minutes_used": None, "included_minutes": None, "minutes_remaining": None,
        "overage_minutes": None, "overage_rate_cents": None, "usage_cents": None,
        "next_invoice_cents": value(preview, "total") if preview is not None else None,
        "next_invoice_at": iso(value(preview, "next_payment_attempt") or end),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if not metered:
        result["note"] = "Your existing plan has no separate metered AI charge. Its pricing has not changed."
        return result
    if len(metered) != 1 or not usage_price or not start or not end:
        raise ValueError("Usage plan could not be identified")
    # Read the actual graduated price rather than applying new terms to old plans.
    tiers = value(usage_price, "tiers", [])
    if (value(usage_price, "tiers_mode") != "graduated" or len(tiers) != 2
        or Decimal(str(value(tiers[0], "unit_amount_decimal", value(tiers[0], "unit_amount", -1)))) != 0
        or any(value(t, "flat_amount", 0) not in (None, 0) for t in tiers)
        or value(tiers[0], "up_to") is None or value(tiers[1], "up_to") is not None):
        raise ValueError("Unsupported usage price")
    included = value(tiers[0], "up_to")
    rate = float(Decimal(str(value(tiers[1], "unit_amount_decimal", value(tiers[1], "unit_amount")))))
    result.update(included_minutes=included, overage_rate_cents=rate)
    if status == "trialing":
        result["note"] = "You are in your free trial. Paid usage tracking and your included minutes begin when the trial ends."
        return result
    if preview is None or value(value(preview, "lines", {}), "has_more", False):
        result["note"] = "The upcoming invoice is temporarily unavailable. Refresh to check again."
        return result
    used = Decimal(0)
    amount = 0
    matched = False
    for line in value(value(preview, "lines", {}), "data", []):
        details = value(value(line, "parent", {}), "subscription_item_details", {})
        line_item = value(details, "subscription_item") or value(line, "subscription_item")
        if line_item != value(first, "id") or value(details, "proration", value(line, "proration", False)):
            continue
        period = value(line, "period", {})
        # Stripe rounds metered invoice periods down to minute boundaries.
        # Compare the same minute without accepting another billing cycle.
        line_start, line_end = value(period, "start"), value(period, "end")
        if line_start is None or line_end is None or line_start // 60 != start // 60 or line_end // 60 != end // 60:
            continue
        quantity = value(line, "quantity_decimal")
        if quantity is None:
            quantity = value(line, "quantity")
        if quantity is None:
            raise ValueError("Missing usage quantity")
        used += Decimal(str(quantity))
        amount += value(line, "amount", 0)
        matched = True
    if not matched:
        result["note"] = "Usage has not appeared on your upcoming invoice yet. Refresh to check again."
        return result
    result.update(usage_available=True, minutes_used=float(used),
        minutes_remaining=float(max(Decimal(0), Decimal(included)-used)),
        overage_minutes=float(max(Decimal(0), used-Decimal(included))), usage_cents=amount)
    result["note"] = "Minutes reflect the usage counted on your upcoming invoice. Recent calls can take a few minutes to appear. Estimates may change with more calls, taxes, discounts, or credits."
    return result
