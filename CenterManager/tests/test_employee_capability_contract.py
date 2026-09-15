# -*- coding: utf-8 -*-
"""Regression tests for explicit Employee Workspace capability enforcement."""
from datetime import date, time, datetime

from sqlalchemy.orm import sessionmaker

from centermanager.core.current_user import CurrentUserContext
from centermanager.database.base import Base
from centermanager.database.engine import create_engine_for_path
from centermanager.models import Employee, User, Role, Permission
from centermanager.repositories.employee_repository import EmployeeRepository
from centermanager.repositories.role_repository import RoleRepository
from centermanager.services.employee_capability_policy import EmployeeCapabilityPolicy
from centermanager.services.employee_schedule_service import (
    EmployeeScheduleService,
    EmployeeScheduleAccessDeniedError,
)
from centermanager.services.employee_working_time_service import (
    EmployeeWorkingTimeService,
    EmployeeWorkingTimeAccessDeniedError,
)


def _session(path):
    engine = create_engine_for_path(path)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as s:
        perms = {
            name: Permission(name=name, description=name, category="employee")
            for name in (
                "schedule.view.all", "schedule.view.self", "schedule.manage",
                "working_time.view.all", "working_time.view.self",
                "working_time.create.self", "working_time.manage", "working_time.lock",
            )
        }
        s.add_all(perms.values())
        s.flush()
        admin_role = Role(name="admin", display_name="Admin", is_system=True, permissions=[])
        manager_role = Role(
            name="manager", display_name="Manager", is_system=True,
            permissions=[perms["schedule.view.all"], perms["working_time.view.all"]],
        )
        schedule_manager_role = Role(
            name="schedule_manager", display_name="Schedule Manager", is_system=False,
            permissions=[perms["schedule.view.all"], perms["schedule.manage"]],
        )
        working_manager_role = Role(
            name="working_manager", display_name="Working Manager", is_system=False,
            permissions=[perms["working_time.view.all"], perms["working_time.manage"], perms["working_time.lock"]],
        )
        teacher_role = Role(
            name="teacher", display_name="Teacher", is_system=True,
            permissions=[perms["schedule.view.self"], perms["working_time.view.self"], perms["working_time.create.self"]],
        )
        s.add_all([admin_role, manager_role, schedule_manager_role, working_manager_role, teacher_role])
        s.commit()
    return Session


def _user(Session, role, username):
    with Session() as s:
        role_obj = RoleRepository(s).get_by_name(role)
        user = User(username=username, password_hash="test", full_name=username,
                    role_id=role_obj.id, is_active=True, force_password_change=False)
        s.add(user); s.commit(); s.refresh(user)
        return user


def _employee(Session, user_id, name="Employee"):
    with Session() as s:
        e = Employee(employee_code=f"EMP-{user_id:05d}", full_name=name,
                     employment_status=Employee.STATUS_ACTIVE, user_id=user_id)
        s.add(e); s.commit(); s.refresh(e)
        return e


def test_admin_is_the_only_implicit_capability_grant():
    class DummyRole:
        def __init__(self, name, permissions=()):
            self.name = name
            self._permissions = set(permissions)

        @property
        def permission_names(self):
            return self._permissions

        def has_permission(self, name):
            return name in self._permissions

    class DummyUser:
        def __init__(self, role):
            self.role = role

        def has_permission(self, name):
            return self.role.has_permission(name)

    admin = DummyUser(DummyRole("admin"))
    manager = DummyUser(DummyRole("manager", {"schedule.view.all"}))
    assert EmployeeCapabilityPolicy.has(admin, "schedule.manage")
    assert not EmployeeCapabilityPolicy.has(manager, "schedule.manage")


def test_schedule_view_all_does_not_grant_schedule_manage(tmp_path):
    Session = _session(tmp_path / "schedule.db")
    manager = _user(Session, "manager", "manager")
    teacher = _user(Session, "teacher", "teacher")
    employee = _employee(Session, teacher.id)
    service = EmployeeScheduleService(Session)
    with CurrentUserContext(manager):
        assert service.can_view_all()
        try:
            service.add_rule(employee.id, 0, time(9), time(10), date(2026, 1, 1))
        except EmployeeScheduleAccessDeniedError as exc:
            assert "schedule.manage" in str(exc)
        else:
            raise AssertionError("schedule.view.all must not grant schedule.manage")


def test_working_time_view_all_does_not_grant_management(tmp_path):
    Session = _session(tmp_path / "working-time.db")
    manager = _user(Session, "manager", "manager")
    teacher = _user(Session, "teacher", "teacher")
    employee = _employee(Session, teacher.id)
    service = EmployeeWorkingTimeService(Session)
    with CurrentUserContext(manager):
        assert service.can_view_all()
        try:
            service.check_in(employee.id, at=datetime(2026, 1, 5, 9, 0))
        except EmployeeWorkingTimeAccessDeniedError as exc:
            assert "working_time.manage" in str(exc)
        else:
            raise AssertionError("working_time.view.all must not grant management")


def test_teacher_create_self_does_not_grant_working_time_manage(tmp_path):
    Session = _session(tmp_path / "working-time-self.db")
    teacher = _user(Session, "teacher", "teacher")
    employee = _employee(Session, teacher.id)
    service = EmployeeWorkingTimeService(Session)
    with CurrentUserContext(teacher):
        entry = service.check_in(employee.id, at=datetime(2026, 1, 5, 9, 0))
        assert entry.employee_id == employee.id
        try:
            service.approve(entry.id)
        except EmployeeWorkingTimeAccessDeniedError as exc:
            assert "working_time.manage" in str(exc)
        else:
            raise AssertionError("working_time.create.self must not grant working_time.manage")
