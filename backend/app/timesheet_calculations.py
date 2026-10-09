"""Scheduled wall-clock hours; appointment occupancy never reduces paid time."""
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP


def union(intervals):
    merged = []
    for start, end in sorted(intervals):
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def seconds(intervals):
    return sum(int((end - start).total_seconds()) for start, end in intervals)


def hours(value):
    return format((Decimal(value) / 3600).quantize(Decimal('.01'), rounding=ROUND_HALF_UP), '.2f')


def calculate_period(week_start, period_end, rules, blocks):
    days = []
    for offset in range((period_end - week_start).days + 1):
        day = week_start + timedelta(days=offset)
        spans = union([(datetime.combine(day, rule.start_time), datetime.combine(day, rule.end_time))
                       for rule in rules if rule.weekday == day.weekday()])
        deductions = []
        for start, end in spans:
            clipped = [(max(start, b['start']), min(end, b['end']), b['reason'], b['scope'])
                       for b in blocks if b['start'] < end and b['end'] > start]
            points = sorted({start, end, *(v for a, z, _, _ in clipped for v in (a, z))})
            for a, z in zip(points, points[1:]):
                reasons = sorted({f"{scope}: {reason}" for x, y, reason, scope in clipped if x < z and y > a})
                if reasons:
                    deductions.append({'start': a.isoformat(), 'end': z.isoformat(),
                                       'seconds': int((z-a).total_seconds()), 'reasons': reasons})
        scheduled = seconds(spans)
        deducted = sum(row['seconds'] for row in deductions)
        days.append({'date': day.isoformat(), 'scheduled_seconds': scheduled,
                     'deducted_seconds': deducted, 'remaining_seconds': scheduled-deducted,
                     'availability': [{'start': a.isoformat(), 'end': z.isoformat()} for a,z in spans],
                     'deductions': deductions})
    return {'days': days, 'scheduled_seconds': sum(d['scheduled_seconds'] for d in days),
            'deducted_seconds': sum(d['deducted_seconds'] for d in days),
            'remaining_seconds': sum(d['remaining_seconds'] for d in days)}


def compensation(row, paid_hours, hourly_rate, commission):
    paid_hours, hourly_rate, commission = map(Decimal, (paid_hours, hourly_rate, commission))
    payable = Decimal(row['remaining_seconds']) / 3600 + paid_hours
    hourly = (payable * hourly_rate).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    return {**row, 'scheduled_hours': hours(row['scheduled_seconds']),
            'deducted_hours': hours(row['deducted_seconds']),
            'remaining_hours': hours(row['remaining_seconds']),
            'paid_hours': format(paid_hours, '.2f'), 'hourly_rate': format(hourly_rate, '.2f'),
            'commission': format(commission, '.2f'),
            'payable_hours': format(payable.quantize(Decimal('.01'), rounding=ROUND_HALF_UP), '.2f'),
            'hourly_compensation': format(hourly, '.2f'),
            'total_compensation': format(hourly+commission, '.2f')}


def calculate_week(week_start, rules, blocks):
    return calculate_period(week_start, week_start + timedelta(days=6), rules, blocks)
