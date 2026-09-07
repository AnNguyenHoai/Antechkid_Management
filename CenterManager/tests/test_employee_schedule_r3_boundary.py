from datetime import date, time, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import sessionmaker

from centermanager.core.current_user import CurrentUserContext
from centermanager.database.base import Base
from centermanager.database.engine import create_engine_for_path
from centermanager.models import User, Role, Employee, Permission
from centermanager.services.employee_capability_policy import EmployeeCapabilityPolicy
from centermanager.services.employee_schedule_service import (
    EmployeeScheduleService,
    EmployeeScheduleAccessDeniedError,
)
from centermanager.services.employee_working_time_service import EmployeeWorkingTimeService


def test_schedule_view_all_does_not_grant_manage(tmp_path):
    engine = create_engine_for_path(tmp_path / "schedule-r3.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as s:
        p_all = Permission(name="schedule.view.all", description="view all", category="employee")
        p_manage = Permission(name="schedule.manage", description="manage", category="employee")
        manager_role = Role(name="manager", display_name="Manager", is_system=True, permissions=[p_all])
        teacher_role = Role(name="teacher", display_name="Teacher", is_system=True)
        s.add_all([p_all, p_manage, manager_role, teacher_role])
        s.flush()
        manager = User(username="manager", password_hash="x", full_name="Manager", role_id=manager_role.id, is_active=True, force_password_change=False)
        teacher = User(username="teacher", password_hash="x", full_name="Teacher", role_id=teacher_role.id, is_active=True, force_password_change=False)
        s.add_all([manager, teacher]); s.flush()
        employee = Employee(employee_code="EMP-00001", full_name="Teacher", employment_status=Employee.STATUS_ACTIVE, user_id=teacher.id)
        s.add(employee); s.commit(); s.refresh(manager); s.refresh(teacher); s.refresh(employee)

    service = EmployeeScheduleService(Session)
    with CurrentUserContext(manager):
        assert service.can_view_all()
        with pytest.raises(EmployeeScheduleAccessDeniedError, match="schedule\.manage"):
            service.add_rule(employee.id, 0, time(9), time(10), date(2026, 9, 1))


def test_schedule_service_full_write_api_is_preserved(tmp_path):
    service = EmployeeScheduleService(lambda: None)
    for name in (
        "list_rules", "list_exceptions", "add_rule", "update_rule", "delete_rule",
        "add_exception", "delete_exception", "expected_for_date",
    ):
        assert hasattr(service, name), f"Missing schedule operation: {name}"


def test_monthly_summary_uses_schedule_with_manager_scope(tmp_path):
    engine = create_engine_for_path(tmp_path / "working-r3.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as s:
        perms = [
            Permission(name=n, description=n, category="employee")
            for n in (
                "working_time.view.all", "working_time.manage", "working_time.lock",
                "schedule.view.all", "schedule.manage",
            )
        ]
        role = Role(name="manager", display_name="Manager", is_system=True, permissions=perms)
        s.add(role); s.flush()
        manager = User(username="manager", password_hash="x", full_name="Manager", role_id=role.id, is_active=True, force_password_change=False)
        s.add(manager); s.flush()
        emp = Employee(employee_code="EMP-00001", full_name="Employee", employment_status=Employee.STATUS_ACTIVE)
        s.add(emp); s.commit(); s.refresh(manager); s.refresh(emp)

    schedule = EmployeeScheduleService(Session)
    working = EmployeeWorkingTimeService(Session, schedule)
    with CurrentUserContext(manager):
        schedule.add_rule(emp.id, 0, time(9), time(12), date(2026, 9, 1), effective_to=None)
        working.create_booking(emp.id, date(2026, 9, 7), time(9), time(12), "TEACHING")
        summary = working.monthly_summary(emp.id, 2026, 9)

    assert summary["actual_minutes"] == 180
    assert summary["expected_minutes"] == 720
    assert summary["overtime_minutes"] == 0
    assert summary["shortfall_minutes"] == 540


def test_monthly_summary_does_not_bypass_schedule_scope(tmp_path):
    class Principal:
        id = 123
        role = SimpleNamespace(name="teacher")
        permissions = {"working_time.view.all"}

        def has_permission(self, name):
            return name in self.permissions

    assert not EmployeeCapabilityPolicy.has(Principal(), "schedule.view.all")
    assert not EmployeeCapabilityPolicy.has(Principal(), "schedule.manage")
