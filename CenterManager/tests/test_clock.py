# -*- coding: utf-8 -*-
"""Tests for deterministic application clock behavior."""

from datetime import date, datetime

from centermanager.core.clock import Clock, get_clock, reset_clock, set_clock


def test_fixed_clock_returns_deterministic_now_and_today():
    fixed_now = datetime(2026, 9, 1, 13, 15, 0)
    fixed_today = date(2026, 9, 1)
    clock = Clock(now_fn=lambda: fixed_now, today_fn=lambda: fixed_today)

    assert clock.now() == fixed_now
    assert clock.now() == fixed_now
    assert clock.today() == fixed_today
    assert clock.today() == fixed_today


def test_application_clock_can_be_injected_and_reset():
    fixed_now = datetime(2030, 1, 2, 8, 30, 45)
    fixed_today = date(2030, 1, 2)
    set_clock(Clock(now_fn=lambda: fixed_now, today_fn=lambda: fixed_today))
    try:
        assert get_clock().now() == fixed_now
        assert get_clock().today() == fixed_today
        assert get_clock() is get_clock()
    finally:
        reset_clock()


def test_reset_clock_restores_system_clock_contract():
    fixed_now = datetime(2035, 5, 6, 7, 8, 9)
    set_clock(Clock(now_fn=lambda: fixed_now, today_fn=lambda: fixed_now.date()))
    reset_clock()

    current = get_clock().now()
    assert current != fixed_now
    assert isinstance(current, datetime)
    assert isinstance(get_clock().today(), date)
