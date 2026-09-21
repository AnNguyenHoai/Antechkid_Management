# -*- coding: utf-8 -*-
"""Regression coverage for deterministic weekly work-registration clock behavior."""

from datetime import date, datetime

from centermanager.core.clock import Clock, reset_clock, set_clock
from centermanager.services.employee_work_registration_service import EmployeeWorkRegistrationService


def test_next_week_uses_application_clock_at_week_boundary():
    set_clock(Clock(now_fn=lambda: datetime(2026, 8, 31, 23, 59, 59), today_fn=lambda: date(2026, 8, 31)))
    try:
        service = EmployeeWorkRegistrationService.__new__(EmployeeWorkRegistrationService)
        assert service.next_week() == date(2026, 9, 7)
    finally:
        reset_clock()


def test_next_week_uses_application_clock_at_year_boundary():
    set_clock(Clock(now_fn=lambda: datetime(2026, 12, 31, 23, 59, 59), today_fn=lambda: date(2026, 12, 31)))
    try:
        service = EmployeeWorkRegistrationService.__new__(EmployeeWorkRegistrationService)
        assert service.next_week() == date(2027, 1, 4)
    finally:
        reset_clock()
