"""Unit tests for the pure add_business_days utility.

NO Django markers, NO database. These run with a plain pytest invocation.
"""

from datetime import date

import pytest

from plane.prodoc.scheduling.business_days import add_business_days


class TestAddBusinessDays:
    def test_skips_weekends(self):
        # Friday April 17, 2026 + 1 working day = Monday April 20, 2026
        assert add_business_days(date(2026, 4, 17), 1, set()) == date(2026, 4, 20)

    def test_skips_holidays(self):
        # Friday April 17 + 1 working day, with Monday April 20 as a holiday
        # → Tuesday April 21
        holidays = {date(2026, 4, 20)}
        assert add_business_days(date(2026, 4, 17), 1, holidays) == date(2026, 4, 21)

    def test_zero_offset_returns_start_unchanged_even_on_weekend(self):
        # Saturday April 18, 2026 + 0 → Saturday April 18, 2026
        assert add_business_days(date(2026, 4, 18), 0, set()) == date(2026, 4, 18)

    def test_zero_offset_returns_start_unchanged_even_on_holiday(self):
        d = date(2026, 4, 14)
        assert add_business_days(d, 0, {d}) == d

    def test_negative_offset_walks_backward_skipping_weekends(self):
        # Monday April 20, 2026 - 1 working day = Friday April 17, 2026
        assert add_business_days(date(2026, 4, 20), -1, set()) == date(2026, 4, 17)

    def test_negative_offset_skips_holidays(self):
        # Monday April 20, 2026 - 1 working day, with Friday April 17 as holiday
        # → Thursday April 16
        holidays = {date(2026, 4, 17)}
        assert add_business_days(date(2026, 4, 20), -1, holidays) == date(2026, 4, 16)

    def test_holiday_on_monday_after_weekend(self):
        # Friday April 17, 2026 + 1 working day, with Monday April 20 as holiday
        # → Tuesday April 21
        holidays = {date(2026, 4, 20)}
        assert add_business_days(date(2026, 4, 17), 1, holidays) == date(2026, 4, 21)

    def test_empty_holiday_set_behaves_as_weekend_only_calendar(self):
        # Multi-week walk: Mon April 13, 2026 + 10 working days
        # = Mon April 27, 2026 (skipping two weekends)
        result = add_business_days(date(2026, 4, 13), 10, set())
        assert result == date(2026, 4, 27)

    def test_overflow_guard_raises_when_every_day_is_a_holiday(self):
        # Block out 400 days starting from start; walking 1 working day
        # forward exceeds the 10*1 + 365 = 375 step guard.
        start = date(2026, 1, 1)
        holidays = {start + __import__("datetime").timedelta(days=i) for i in range(1, 400)}
        with pytest.raises(ValueError):
            add_business_days(start, 1, holidays)

    def test_holidays_can_be_passed_as_list(self):
        # Set conversion happens internally; both should work.
        holidays_list = [date(2026, 4, 20)]
        assert add_business_days(date(2026, 4, 17), 1, holidays_list) == date(2026, 4, 21)

    def test_type_error_on_non_date_start(self):
        with pytest.raises(TypeError):
            add_business_days("2026-04-17", 1, set())

    def test_type_error_on_non_int_n_days(self):
        with pytest.raises(TypeError):
            add_business_days(date(2026, 4, 17), 1.5, set())
