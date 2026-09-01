# -*- coding: utf-8 -*-
"""Employee domain application service and access-control boundary."""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional, List

from sqlalchemy.orm import sessionmaker

from centermanager.models.employee import Employee
from centermanager.models.role import RoleDefinitions
from centermanager.models.user import User
from centermanager.repositories.employee_repository import EmployeeRepository
from centermanager.repositories.role_repository import RoleRepository
from centermanager.repositories.user_repository import UserRepository
from centermanager.core.current_user import get_current_user
from centermanager.core.clock import get_clock

logger = logging.getLogger(__name__)


class EmployeeServiceError(Exception):
    pass


class EmployeeNotFoundError(EmployeeServiceError):
    pass


class EmployeeValidationError(EmployeeServiceError):
    pass


class EmployeeAccessDeniedError(EmployeeServiceError):
    pass


class EmployeeService:
    """Employee business service with self/all data-level authorization."""

    def __init__(self, session_factory: sessionmaker):
        self._session_factory = session_factory

    @staticmethod
    def _text(v):
        if v is None:
            return None
        v = v.strip()
        return v or None

    def _validate_status(self, status):
        status = (self._text(status) or Employee.STATUS_ACTIVE).upper()
        if status not in Employee.VALID_STATUSES:
            raise EmployeeValidationError(f"Invalid employment status: {status}")
        return status

    @staticmethod
    def _is_manager_or_admin(user: Optional[User]) -> bool:
        return bool(user and user.role and user.role.name in {
            RoleDefinitions.ADMIN,
            RoleDefinitions.MANAGER,
        })

    @staticmethod
    def _require_user(user: Optional[User]) -> User:
        user = user or get_current_user()
        if user is None:
            raise EmployeeAccessDeniedError("Authentication is required.")
        return user

    def can_view_all(self, user: Optional[User] = None) -> bool:
        user = self._require_user(user)
        return self._is_manager_or_admin(user) or user.has_permission("employee.view.all")

    def can_view_self(self, user: Optional[User] = None) -> bool:
        user = self._require_user(user)
        if self.can_view_all(user) or user.has_permission("employee.view.self"):
            return True
        with self._session_factory() as session:
            return EmployeeRepository(session).get_by_user_id(user.id) is not None

    def can_access_workspace(self, user: Optional[User] = None) -> bool:
        user = self._require_user(user)
        return self.can_view_all(user) or self.can_view_self(user)

    def _require_management(self, user: Optional[User] = None) -> User:
        user = self._require_user(user)
        if not self._is_manager_or_admin(user):
            raise EmployeeAccessDeniedError(
                "Only administrators and managers can perform employee management actions."
            )
        return user

    def get_current_employee(self, user: Optional[User] = None) -> Employee:
        """Resolve the employee identity from the authenticated account."""
        user = self._require_user(user)
        with self._session_factory() as session:
            employee = EmployeeRepository(session).get_by_user_id(user.id)
            if employee:
                return employee
            repo = EmployeeRepository(session)
            number = (repo.get_highest_employee_number() or 0) + 1
            employee = Employee(
                employee_code=f"EMP-{number:05d}",
                full_name=user.full_name,
                phone=user.phone,
                email=user.email,
                employment_status=Employee.STATUS_ACTIVE,
                user_id=user.id,
            )
            repo.add(employee)
            session.commit()
            session.refresh(employee)
            logger.info(
                "Repaired legacy user-to-employee link: user_id=%s employee_id=%s",
                user.id, employee.id,
            )
            return employee

    def list_visible_employees(self, user: Optional[User] = None) -> List[Employee]:
        """Return only records the authenticated user is authorized to see."""
        user = self._require_user(user)
        with self._session_factory() as session:
            repo = EmployeeRepository(session)
            if self.can_view_all(user):
                return repo.list_all()
            if self.can_view_self(user):
                employee = repo.get_by_user_id(user.id)
                return [employee] if employee else []
            raise EmployeeAccessDeniedError(
                "You do not have permission to view employee information."
            )

    def get_employee_for_user(self, employee_id: int, user: Optional[User] = None) -> Employee:
        """Get one employee while enforcing self/all visibility at service level."""
        user = self._require_user(user)
        with self._session_factory() as session:
            repo = EmployeeRepository(session)
            employee = repo.get_by_id(employee_id)
            if employee is None:
                raise EmployeeNotFoundError(f"Employee {employee_id} not found.")
            if self.can_view_all(user) or employee.user_id == user.id:
                return employee
            raise EmployeeAccessDeniedError(
                "You can only access your own employee profile."
            )

    def get_or_create_employee_for_user(self, user: Optional[User] = None) -> Employee:
        """Resolve the authenticated employee, repairing a legacy account when safe."""
        user = self._require_user(user)
        with self._session_factory() as session:
            repo = EmployeeRepository(session)
            employee = repo.get_by_user_id(user.id)
            if employee:
                return employee
            number = (repo.get_highest_employee_number() or 0) + 1
            employee = Employee(
                employee_code=f"EMP-{number:05d}",
                full_name=user.full_name,
                phone=user.phone,
                email=user.email,
                employment_status=Employee.STATUS_ACTIVE,
                user_id=user.id,
            )
            repo.add(employee)
            session.commit()
            session.refresh(employee)
            return employee

    def create_employee(
        self, full_name: str, *, date_of_birth: Optional[date] = None,
        gender=None, phone=None, email=None, address=None, department=None,
        position=None, employment_status=Employee.STATUS_ACTIVE,
        hire_date: Optional[date] = None, user_id: Optional[int] = None,
    ) -> Employee:
        """Create a linked employee. New employees must have an account."""
        self._require_management()
        if user_id is None:
            raise EmployeeValidationError(
                "An employee account is required. Create or select a user account first."
            )
        full_name = self._text(full_name)
        if not full_name:
            raise EmployeeValidationError("Full name is required.")
        if email := self._text(email):
            if "@" not in email:
                raise EmployeeValidationError("Invalid email format.")
        status = self._validate_status(employment_status)
        with self._session_factory() as s:
            repo = EmployeeRepository(s)
            user_repo = UserRepository(s)
            if user_repo.get_by_id_with_role(user_id) is None:
                raise EmployeeValidationError("Selected user account does not exist.")
            if repo.get_by_user_id(user_id):
                raise EmployeeValidationError("User is already linked to an employee.")
            n = (repo.get_highest_employee_number() or 0) + 1
            e = Employee(
                employee_code=f"EMP-{n:05d}",
                full_name=full_name,
                date_of_birth=date_of_birth,
                gender=self._text(gender),
                phone=self._text(phone),
                email=email,
                address=self._text(address),
                department=self._text(department),
                position=self._text(position),
                employment_status=status,
                hire_date=hire_date or get_clock().today(),
                user_id=user_id,
            )
            repo.add(e)
            s.commit()
            s.refresh(e)
            return e

    def create_employee_with_account(
        self, full_name: str, username: str, role_name: str, *,
        temp_password: Optional[str] = None, date_of_birth: Optional[date] = None,
        gender=None, phone=None, email=None, address=None, department=None,
        position=None, employment_status=Employee.STATUS_ACTIVE,
        hire_date: Optional[date] = None,
    ):
        """Atomically create an employee and its mandatory login account."""
        actor = self._require_management()
        from centermanager.security.password import hash_password
        import secrets, string

        username = self._text(username)
        if not username:
            raise EmployeeValidationError("Username is required.")
        if role_name not in RoleDefinitions.all_roles():
            raise EmployeeValidationError(f"Invalid account role: {role_name}")
        if actor.role and actor.role.name == RoleDefinitions.MANAGER and role_name in {
            RoleDefinitions.ADMIN, RoleDefinitions.MANAGER
        }:
            raise EmployeeAccessDeniedError("Managers cannot create administrator or manager accounts.")

        full_name = self._text(full_name)
        if not full_name:
            raise EmployeeValidationError("Full name is required.")
        if email := self._text(email):
            if "@" not in email:
                raise EmployeeValidationError("Invalid email format.")
        status = self._validate_status(employment_status)

        with self._session_factory() as s:
            user_repo = UserRepository(s)
            if user_repo.get_by_username(username):
                raise EmployeeValidationError(f"Username '{username}' already exists.")
            role = RoleRepository(s).get_by_name(role_name)
            if role is None:
                raise EmployeeValidationError(f"Role '{role_name}' not found.")

            if temp_password is None:
                alphabet = string.ascii_letters + string.digits
                temp_password = "".join(secrets.choice(alphabet) for _ in range(10))

            user = User(
                username=username,
                password_hash=hash_password(temp_password),
                full_name=full_name,
                email=email,
                phone=self._text(phone),
                role_id=role.id,
                is_active=True,
                force_password_change=True,
                login_attempts=0,
            )
            user_repo.add(user)
            s.flush()

            repo = EmployeeRepository(s)
            n = (repo.get_highest_employee_number() or 0) + 1
            employee = Employee(
                employee_code=f"EMP-{n:05d}",
                full_name=full_name,
                date_of_birth=date_of_birth,
                gender=self._text(gender),
                phone=self._text(phone),
                email=email,
                address=self._text(address),
                department=self._text(department),
                position=self._text(position),
                employment_status=status,
                hire_date=hire_date or get_clock().today(),
                user_id=user.id,
            )
            repo.add(employee)
            s.commit()
            s.refresh(employee)
            employee._temporary_password = temp_password
            employee._account_username = username
            return employee

    def link_existing_user(self, employee_id: int, user_id: int) -> Employee:
        self._require_management()
        with self._session_factory() as s:
            repo = EmployeeRepository(s)
            employee = repo.get_by_id(employee_id)
            if not employee:
                raise EmployeeNotFoundError(f"Employee {employee_id} not found.")
            if employee.user_id is not None and employee.user_id != user_id:
                raise EmployeeValidationError("Employee is already linked to an account.")
            existing = repo.get_by_user_id(user_id)
            if existing and existing.id != employee_id:
                raise EmployeeValidationError("User is already linked to another employee.")
            if UserRepository(s).get_by_id_with_role(user_id) is None:
                raise EmployeeValidationError("User account does not exist.")
            employee.user_id = user_id
            s.commit()
            s.refresh(employee)
            return employee

    def get_employee(self, employee_id: int, user: Optional[User] = None) -> Employee:
        """Authorized employee lookup. Never exposes an arbitrary employee to self-service users."""
        return self.get_employee_for_user(employee_id, user)

    def list_employees(self) -> List[Employee]:
        """Legacy management API; callers should prefer list_visible_employees."""
        return self.list_visible_employees()

    def update_status(self, employee_id: int, status: str, termination_date: Optional[date] = None) -> Employee:
        self._require_management()
        with self._session_factory() as s:
            e = EmployeeRepository(s).get_by_id(employee_id)
            if not e:
                raise EmployeeNotFoundError(f"Employee {employee_id} not found.")
            e.employment_status = self._validate_status(status)
            e.termination_date = termination_date
            s.commit()
            s.refresh(e)
            return e

    def update_employee(self, employee_id: int, **data) -> Employee:
        actor = self._require_user(None)
        with self._session_factory() as s:
            e = EmployeeRepository(s).get_by_id(employee_id)
            if not e:
                raise EmployeeNotFoundError(f"Employee {employee_id} not found.")
            is_self = e.user_id == actor.id
            is_management = self.can_view_all(actor)
            if not is_management and not is_self:
                raise EmployeeAccessDeniedError("You can only update your own employee profile.")
            if is_management:
                if not actor.has_permission("employee.update") and not self._is_manager_or_admin(actor):
                    raise EmployeeAccessDeniedError("Permission 'employee.update' is required.")
            else:
                if not (
                    actor.has_permission("employee.update.self")
                    or actor.has_permission("employee.view.self")
                ):
                    raise EmployeeAccessDeniedError("Permission 'employee.update.self' is required.")
                forbidden = set(data) - {"full_name", "phone", "email", "address", "date_of_birth", "gender"}
                if forbidden:
                    raise EmployeeAccessDeniedError(
                        "Employees may only update personal profile information."
                    )
            for key in ("full_name", "phone", "email", "address", "department", "position", "gender"):
                if key in data:
                    setattr(e, key, self._text(data[key]))
            if "full_name" in data and not e.full_name:
                raise EmployeeValidationError("Full name is required.")
            if e.email and "@" not in e.email:
                raise EmployeeValidationError("Invalid email format.")
            if "employment_status" in data:
                e.employment_status = self._validate_status(data["employment_status"])
            if "hire_date" in data:
                e.hire_date = data["hire_date"]
            s.commit()
            s.refresh(e)
            return e
