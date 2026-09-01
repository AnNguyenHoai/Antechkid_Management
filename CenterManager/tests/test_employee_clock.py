# -*- coding: utf-8 -*-
"""Regression tests for EmployeeService planning-date determinism."""

from datetime import date

from centermanager.core.clock import Clock, reset_clock, set_clock
from centermanager.models.employee import Employee
from centermanager.models.role import RoleDefinitions
from centermanager.services.employee_service import EmployeeService


def test_create_employee_defaults_hire_date_to_injected_today(monkeypatch, tmp_path):
    """EmployeeService must use the application clock for the default hire date."""
    fixed_today = date(2040, 4, 5)
    set_clock(Clock(today_fn=lambda: fixed_today))

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def commit(self):
            pass

        def refresh(self, obj):
            pass

    class FakeRepo:
        def get_by_user_id(self, user_id):
            return None

        def get_highest_employee_number(self):
            return 0

        def add(self, employee):
            self.employee = employee

    fake_repo = FakeRepo()

    monkeypatch.setattr(
        "centermanager.services.employee_service.EmployeeRepository",
        lambda session: fake_repo,
    )
    monkeypatch.setattr(
        "centermanager.services.employee_service.UserRepository",
        lambda session: type("Users", (), {"get_by_id_with_role": lambda self, user_id: object()})(),
    )

    actor = type(
        "Actor",
        (),
        {
            "role": type("Role", (), {"name": RoleDefinitions.ADMIN})(),
            "has_permission": lambda self, permission: True,
        },
    )()

    service = EmployeeService(lambda: FakeSession())
    employee = service.create_employee(
        "Clock Test",
        user_id=99,
    )
    try:
        assert employee.hire_date == fixed_today
    finally:
        reset_clock()


def test_explicit_hire_date_is_not_overridden_by_clock():
    explicit_date = date(2050, 10, 20)
    clock_date = date(2050, 10, 21)
    set_clock(Clock(today_fn=lambda: clock_date))

    assert explicit_date != clock_date
    reset_clock()
