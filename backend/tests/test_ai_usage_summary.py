from app.ai_usage_summary import summarize


def fixtures():
    price = {'id': 'usage', 'recurring': {'usage_type': 'metered'}, 'tiers_mode': 'graduated', 'tiers': [
        {'up_to': 250, 'unit_amount_decimal': '0'}, {'up_to': None, 'unit_amount_decimal': '29'}]}
    sub = {'status': 'active', 'currency': 'usd', 'items': {'data': [
        {'id': 'core', 'price': {'unit_amount': 4900, 'recurring': {'interval': 'month'}}},
        {'id': 'ai', 'price': {'unit_amount': 4900, 'recurring': {'interval': 'month'}}},
        {'id': 'meter', 'price': price, 'current_period_start': 1800000000, 'current_period_end': 1802678400}]}}
    def line(q, amount, item='meter', start=1800000000):
        return {'quantity': q, 'amount': amount, 'period': {'start': start, 'end': 1802678400},
                'parent': {'subscription_item_details': {'subscription_item': item, 'proration': False}}}
    invoice = {'total': 17050, 'lines': {'data': [line(250, 0), line(0, 0), line(250, 7250), line(1, 4900, 'ai'), line(1, 4900, 'core')]}}
    return sub, invoice, price


def test_overage_matches_invoice():
    result = summarize(*fixtures())
    assert result['minutes_used'] == 500
    assert result['minutes_remaining'] == 0
    assert result['overage_minutes'] == 250
    assert result['usage_cents'] == 7250
    assert result['monthly_base_cents'] == 9800
    assert result['next_invoice_cents'] == 17050


def test_different_period_is_not_reported_as_zero():
    sub, invoice, price = fixtures()
    for line in invoice['lines']['data']:
        line['period']['start'] -= 86400
    result = summarize(sub, invoice, price)
    assert not result['usage_available']
    assert result['minutes_used'] is None


def test_zero_and_remaining():
    sub, invoice, price = fixtures()
    invoice['lines']['data'] = [invoice['lines']['data'][0]]
    invoice['lines']['data'][0]['quantity'] = 0
    result = summarize(sub, invoice, price)
    assert result['usage_available'] and result['minutes_remaining'] == 250


def test_trial_does_not_claim_paid_usage():
    sub, invoice, price = fixtures()
    sub['status'] = 'trialing'
    result = summarize(sub, invoice, price)
    assert result['minutes_used'] is None and not result['usage_available']


def test_legacy_terms_preserved():
    sub, invoice, price = fixtures()
    sub['items']['data'].pop()
    sub['items']['data'][1]['price']['unit_amount'] = 14900
    result = summarize(sub, invoice)
    assert not result['metered'] and result['monthly_base_cents'] == 19800
    assert result['included_minutes'] is None


def test_partial_preview_is_unavailable():
    sub, invoice, price = fixtures()
    invoice['lines']['has_more'] = True
    assert summarize(sub, invoice, price)['minutes_used'] is None


def test_unsupported_price_rejected():
    sub, invoice, price = fixtures()
    price['tiers_mode'] = 'volume'
    try:
        summarize(sub, invoice, price)
    except ValueError:
        return
    raise AssertionError("Unsupported price was accepted")
