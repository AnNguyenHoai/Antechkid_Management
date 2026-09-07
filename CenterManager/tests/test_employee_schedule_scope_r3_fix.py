from datetime import date, time

import pytest
from sqlalchemy.orm import sessionmaker

from centermanager.core.current_user import CurrentUserContext
from centermanager.database.base import Base
from centermanager.database.engine import create_engine_for_path
from centermanager.models import Employee, Permission, Role, User
from centermanager.repositories.role_repository import RoleRepository
from centermanager.services.employee_capability_policy import EmployeeCapabilityPolicy
from centermanager.services.employee_schedule_service import (
    EmployeeScheduleAccessDeniedError,
    EmployeeScheduleService,
)


def _db(tmp_path):
    engine = create_engine_for_path(tmp_path / "schedule-r3-fix.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as s:
        perms = {
            name: Permission(name=name, description=name, category="employee")
            for name in ("schedule.view.all", "schedule.view.self", "schedule.manage")
        }
        manager_role = Role(name="manager", display_name="Manager", is_system=True,
                            permissions=[perms["schedule.view.all"]])
        schedule_manager_role = Role(
            name="schedule_manager", display_name="Schedule Manager", is_system=False,
            permissions=[perms["schedule.view.all"], perms["schedule.manage"]],
        )
        teacher_role = Role(name="teacher", display_name="Teacher", is_system=True,
                            permissions=[perms["schedule.view.self"]])
        s.add_all([*perms.values(), manager_role, schedule_manager_role, teacher_role])
        s.commit()
    return Session


def _user(Session, role, username):
    with Session() as s:
        role_obj = RoleRepository(s).get_by_name(role)
        user = User(username=username, password_hash="test", full_name=username,
                    role_id=role_obj.id, is_active=True, force_password_change=False)
        s.add(user)
        s.commit()
        s.refresh(user)
        return user


def _employee(Session, user_id):
    with Session() as s:
        employee = Employee(
            employee_code=f"EMP-{user_id:05d}",
            full_name="Teacher",
            employment_status=Employee.STATUS_ACTIVE,
            user_id=user_id,
        )
        s.add(employee)
        s.commit()
        s.refresh(employee)
        return employee


def test_manager_view_all_does_not_grant_schedule_manage(tmp_path):
    Session = _db(tmp_path)
    manager = _user(Session, "manager", "manager")
    teacher = _user(Session, "teacher", "teacher")
    employee = _employee(Session, teacher.id)
    service = EmployeeScheduleService(Session)

    with CurrentUserContext(manager):
        assert service.can_view_all()
        with pytest.raises(EmployeeScheduleAccessDeniedError, match=r"schedule\.manage"):
            service.add_rule(employee.id, 0, time(9), time(10), date(2026, 9, 1))


def test_schedule_manage_is_explicit_capability(tmp_path):
    Session = _db(tmp_path)
    schedule_manager = _user(Session, "schedule_manager", "schedule-manager")
    teacher = _user(Session, "teacher", "teacher")
    employee = _employee(Session, teacher.id)
    service = EmployeeScheduleService(Session)

    assert EmployeeCapabilityPolicy.has(schedule_manager, "schedule.manage")
    with CurrentUserContext(schedule_manager):
        rule = service.add_rule(employee.id, 0, time(9), time(12), date(2026, 9, 1))
        assert rule.employee_id == employee.id
