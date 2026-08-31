# -*- coding: utf-8 -*-
"""Employee 1.2 access-control and self-service regression tests."""
from sqlalchemy.orm import sessionmaker

from centermanager.database.base import Base
from centermanager.database.engine import create_engine_for_path
from centermanager.database.seed import seed_roles_and_permissions
from centermanager.models import Employee, User, Role, Permission
from centermanager.models.role import RoleDefinitions
from centermanager.repositories.role_repository import RoleRepository
from centermanager.services.employee_service import (
    EmployeeService, EmployeeAccessDeniedError, EmployeeValidationError,
)
from centermanager.core.current_user import CurrentUserContext


def _session(path):
    engine = create_engine_for_path(path)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as s:
        all_perm = Permission(name="employee.view.all", description="all", category="employee")
        self_perm = Permission(name="employee.view.self", description="self", category="employee")
        s.add_all([all_perm, self_perm])
        s.flush()
        manager_role = Role(
            name=RoleDefinitions.MANAGER, display_name="Manager",
            description="test role", is_system=True, permissions=[all_perm, self_perm]
        )
        teacher_role = Role(
            name=RoleDefinitions.TEACHER, display_name="Teacher",
            description="test role", is_system=True, permissions=[self_perm]
        )
        s.add_all([manager_role, teacher_role])
        s.commit()
    return Session


def _user(Session, role_name, username):
    with Session() as s:
        role = RoleRepository(s).get_by_name(role_name)
        user = User(
            username=username, password_hash="test", full_name=username,
            role_id=role.id, is_active=True, force_password_change=False,
        )
        s.add(user)
        s.commit()
        s.refresh(user)
        return user


def _employee(Session, user_id, name):
    service = EmployeeService(Session)
    return service.create_employee(name, user_id=user_id)


def test_manager_sees_all_and_employee_sees_only_self(tmp_path):
    Session = _session(tmp_path / "access.db")
    manager = _user(Session, RoleDefinitions.MANAGER, "manager")
    teacher = _user(Session, RoleDefinitions.TEACHER, "teacher")
    teacher2 = _user(Session, RoleDefinitions.TEACHER, "teacher2")

    # Management creates linked employee records.
    with CurrentUserContext(manager):
        first = _employee(Session, teacher.id, "Teacher One")
        second = _employee(Session, teacher2.id, "Teacher Two")
        service = EmployeeService(Session)
        assert {e.id for e in service.list_visible_employees()} == {first.id, second.id}

    with CurrentUserContext(teacher):
        service = EmployeeService(Session)
        visible = service.list_visible_employees()
        assert [e.id for e in visible] == [first.id]
        assert service.get_employee_for_user(first.id).id == first.id
        try:
            service.get_employee_for_user(second.id)
        except EmployeeAccessDeniedError:
            pass
        else:
            raise AssertionError("Teacher must not access another employee")


def test_new_employee_requires_account(tmp_path):
    Session = _session(tmp_path / "account.db")
    manager = _user(Session, RoleDefinitions.MANAGER, "manager")
    with CurrentUserContext(manager):
        try:
            EmployeeService(Session).create_employee("Unlinked")
        except EmployeeValidationError as exc:
            assert "account is required" in str(exc)
        else:
            raise AssertionError("Unlinked employee creation must be rejected")


def test_employee_can_update_only_safe_self_fields(tmp_path):
    Session = _session(tmp_path / "update.db")
    manager = _user(Session, RoleDefinitions.MANAGER, "manager")
    teacher = _user(Session, RoleDefinitions.TEACHER, "teacher")
    with CurrentUserContext(manager):
        employee = _employee(Session, teacher.id, "Teacher")
    with CurrentUserContext(teacher):
        service = EmployeeService(Session)
        service.update_employee(employee.id, phone="0900000000", address="New address")
        try:
            service.update_employee(employee.id, position="Manager")
        except EmployeeAccessDeniedError:
            pass
        else:
            raise AssertionError("Self user must not change employment fields")


def test_linked_employee_can_access_self_service_without_stale_role_permission(tmp_path):
    Session = _session(tmp_path / "fallback.db")
    manager = _user(Session, RoleDefinitions.MANAGER, "manager")
    teacher = _user(Session, RoleDefinitions.TEACHER, "teacher")
    with CurrentUserContext(manager):
        employee = _employee(Session, teacher.id, "Teacher")
    with CurrentUserContext(teacher):
        service = EmployeeService(Session)
        assert service.can_access_workspace(teacher)
        assert service.get_current_employee(teacher).id == employee.id
