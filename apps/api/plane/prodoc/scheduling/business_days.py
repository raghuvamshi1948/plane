"""
Pure business-day arithmetic. NO Django imports.

This module is intentionally trivial and free of framework dependencies
so the cascade math can be unit-tested in isolation, swapped out for a
faster implementation later (e.g. numpy.busday_offset), and reused by
Extension 3's template materializer without introducing circular
imports.

Semantics summary:

    add_business_days(start, n_days, holidays)

    n_days == 0  → return start unchanged, even if start is a weekend
                   or holiday. Project start is project start; we do
                   not silently shift it.
    n_days  > 0  → walk forward, counting only working days
                   (Mon-Fri AND not in holidays).
    n_days  < 0  → walk backward, same skip rules.

    holidays may be any iterable of datetime.date; for hot paths, pass
    a `set` for O(1) membership checks.

The walk has a guard: at most 10 * |n_days| + 365 day-steps before
ValueError. This catches calendars where every day is a holiday (a bug
or a misload) without hanging the cascade.
"""

from datetime import date, timedelta


def add_business_days(start_date, n_days, holidays):
    if not isinstance(start_date, date):
        raise TypeError("start_date must be a datetime.date")
    if not isinstance(n_days, int):
        raise TypeError("n_days must be an int")
    if n_days == 0:
        return start_date

    # Normalize holidays to a set for O(1) lookup if it isn't one already.
    holiday_set = holidays if isinstance(holidays, set) else set(holidays)

    step = 1 if n_days > 0 else -1
    target = abs(n_days)
    counted = 0
    current = start_date
    max_walk = 10 * target + 365
    walked = 0

    while counted < target:
        current = current + timedelta(days=step)
        walked += 1
        if walked > max_walk:
            raise ValueError(
                f"add_business_days walked {walked} days without finding "
                f"{target} working days; check the holiday set."
            )
        # weekday() is 0=Mon ... 6=Sun
        if current.weekday() >= 5:
            continue
        if current in holiday_set:
            continue
        counted += 1

    return current


def count_business_days(start_date, end_date, holidays):
    """Count working days strictly between start_date and end_date.

    Returns a signed int: positive when end > start, negative when
    end < start, zero when equal.

    Used by the cascade to express "how many working days did the
    blocker slip?" so the same working-day count can be applied to
    downstream items via add_business_days.
    """
    if not isinstance(start_date, date) or not isinstance(end_date, date):
        raise TypeError("start_date and end_date must be datetime.date")
    if start_date == end_date:
        return 0

    holiday_set = holidays if isinstance(holidays, set) else set(holidays)

    if end_date > start_date:
        sign = 1
        first, last = start_date, end_date
    else:
        sign = -1
        first, last = end_date, start_date

    count = 0
    current = first
    while current < last:
        current = current + timedelta(days=1)
        if current.weekday() >= 5:
            continue
        if current in holiday_set:
            continue
        count += 1
    return sign * count
