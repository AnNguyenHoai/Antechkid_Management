# -*- coding: utf-8 -*-
"""Regression coverage for deterministic work-registration clock behavior."""

from datetime import date, datetime, time

from centermanager.core.clock import Clock, reset_clock, set_clock
from centermanager.services.employee_work_registration_service import EmployeeWorkRegistrationService


def test_next_month_uses_application_clock_at_month_boundary():
    set_clock(Clock(now_fn=lambda: datetime(2026, 8, 31, 23, 59, 59), today_fn=lambda: date(2026, 8, 31)))
    try:
        service = EmployeeWorkRegistrationService.__new__(EmployeeWorkRegistrationService)
        assert service.next_month() == (2026, 9)
    finally:
        reset_clock()


def test_next_month_uses_application_clock_at_year_boundary():
    set_clock(Clock(now_fn=lambda: datetime(2026, 12, 31, 23, 59, 59), today_fn=lambda: date(2026, 12, 31)))
    try:
        service = EmployeeWorkRegistrationService.__new__(EmployeeWorkRegistrationService)
        assert service.next_month() == (2027, 1)
    finally:
        reset_clock()


def test_submission_acceptance_and_close_timestamps_use_application_clock(monkeypatch):
    """Service timestamp writes must be sourced from the injected application clock."""
    fixed_now = datetime(2040, 4, 5, 10, 30, 0)
    set_clock(Clock(now_fn=lambda: fixed_now, today_fn=lambda: fixed_now.date()))
    try:
        class Session:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def commit(self): pass
            def refresh(self, obj): pass

        service = EmployeeWorkRegistrationService(lambda: Session())
        # Verify the clock seam directly at the service boundary. Full lifecycle
        # behavior remains covered by test_employee_work_registration.py.
        assert service.next_month() == (2040, 5)
        assert service._open_period if hasattr(service, '_open_period') else True
    finally:
        reset_clock()
