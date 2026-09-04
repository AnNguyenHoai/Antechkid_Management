# -*- coding: utf-8 -*-
"""Regression test for EmployeeService planning-date determinism."""

from datetime import date
from types import SimpleNamespace

from centermanager.core.clock import Clock, reset_clock, set_clock
from centermanager.models.role import RoleDefinitions
from centermanager.services.employee_service import EmployeeService


def test_create_employee_defaults_hire_date_to_injected_today(monkeypatch):
    """EmployeeService must use the application clock for a default hire date."""
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
            employee.id = 1

    class FakeUserRepo:
        def get_by_id_with_role(self, user_id):
            # create_employee() accepts a linked employee-bearing account. Keep
            # this fixture explicit so it does not rely on an untyped object.
            return SimpleNamespace(
                id=user_id,
                role=SimpleNamespace(name=RoleDefinitions.TEACHER),
            )

    actor = type(
        "Actor",
        (),
        {
            "role": type("Role", (), {"name": RoleDefinitions.ADMIN})(),
            "has_permission": lambda self, permission: True,
        },
    )()

    monkeypatch.setattr(
        "centermanager.services.employee_service.EmployeeRepository",
        lambda session: FakeRepo(),
    )
    monkeypatch.setattr(
        "centermanager.services.employee_service.UserRepository",
        lambda session: FakeUserRepo(),
    )
    monkeypatch.setattr(
        "centermanager.services.employee_service.get_current_user",
        lambda: actor,
    )

    service = EmployeeService(lambda: FakeSession())
    employee = service.create_employee("Clock Test", user_id=99)
    try:
        assert employee.hire_date == fixed_today
    finally:
        reset_clock()
