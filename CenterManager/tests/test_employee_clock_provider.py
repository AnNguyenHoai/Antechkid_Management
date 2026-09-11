# -*- coding: utf-8 -*-
"""Regression test for EmployeeService planning-date determinism."""

from datetime import date
from types import SimpleNamespace

from centermanager.core.clock import Clock, reset_clock, set_clock
from centermanager.models.role import RoleDefinitions
from centermanager.services.employee_service import EmployeeService


def test_create_employee_defaults_hire_date_to_injected_today():
    fixed_today = date(2040, 4, 5)
    set_clock(Clock(today_fn=lambda: fixed_today))

    class FakeSession:
        def __enter__(self): return self
        def __exit__(self, exc_type, exc, tb): return False
        def commit(self): pass
        def refresh(self, obj): pass

    class FakeRepo:
        def get_by_user_id(self, user_id): return None
        def get_highest_employee_number(self): return 0
        def add(self, employee): employee.id = 1

    class FakeUserRepo:
        def get_by_id_with_role(self, user_id):
            return SimpleNamespace(
                id=user_id,
                role=SimpleNamespace(name=RoleDefinitions.TEACHER),
            )

    class FakeProvider:
        def employees(self, session): return FakeRepo()
        def users(self, session): return FakeUserRepo()

    actor = type(
        "Actor", (), {
            "role": type("Role", (), {"name": RoleDefinitions.ADMIN})(),
            "has_permission": lambda self, permission: True,
        }
    )()

    import centermanager.services.employee_service as module
    original = module.get_current_user
    module.get_current_user = lambda: actor
    try:
        service = EmployeeService(lambda: FakeSession(), repository_provider=FakeProvider())
        employee = service.create_employee("Clock Test", user_id=99)
        assert employee.hire_date == fixed_today
    finally:
        module.get_current_user = original
        reset_clock()
