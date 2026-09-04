from __future__ import annotations

"""Administrative boundary for Employee Work Registration data management.

This service is intentionally separate from the employee self-service flow.  An
administrator may override a closed registration period and remove registration
or employee records, while every privileged/destructive operation is audited.

The contract is deliberately narrow:
* only an administrator may call these operations;
* reopening a period is an explicit administrative override;
* deleting a registration is an aggregate delete (its blocks follow the ORM
  cascade) and does not delete the period;
* an Employee may be hard-deleted only when it has no operational history.  A
  historical employee must be archived instead of destroying related records.
"""

from typing import Optional

from sqlalchemy import select

from centermanager.core.clock import get_clock
from centermanager.core.current_user import get_current_user
from centermanager.models.employee import Employee
from centermanager.models.employee_work_registration import EmployeeWorkRegistration
from centermanager.models.employee_work_registration_period import (
    EmployeeWorkRegistrationPeriod,
)
from centermanager.models.role import RoleDefinitions
from centermanager.models.user import User
from centermanager.repositories.employee_repository import EmployeeRepository
from centermanager.repositories.employee_work_registration_repository import (
    EmployeeWorkRegistrationRepository,
)
from centermanager.services.audit_service import AuditService
from centermanager.services.permission_service import PermissionService


class EmployeeAdminManagementError(Exception):
    """Base error for administrator-only work-registration data operations."""


class EmployeeAdminManagementAccessDeniedError(EmployeeAdminManagementError):
    """Raised when the actor is not an administrator."""


class EmployeeAdminManagementValidationError(EmployeeAdminManagementError):
    """Raised when an administrative operation violates the data contract."""


class EmployeeAdminManagementService:
    """Admin-only lifecycle and data-management boundary."""

    AUDIT_MODULE = "employee_work_registration_admin"

    ACTION_PERIOD_REOPENED = "WORK_REGISTRATION_PERIOD_ADMIN_REOPENED"
    ACTION_REGISTRATION_DELETED = "WORK_REGISTRATION_ADMIN_DELETED"
    ACTION_EMPLOYEE_DELETED = "EMPLOYEE_ADMIN_DELETED"

    # Stable capability names for future role/permission wiring.  The Admin
    # system role is the only role allowed to exercise these capabilities today.
    CAPABILITY_PERIOD_OVERRIDE = "work_registration.period.admin_override"
    CAPABILITY_REGISTRATION_DELETE = "work_registration.delete"
    CAPABILITY_EMPLOYEE_DELETE = "employee.delete"

    def __init__(self, session_factory):
        self._session_factory = session_factory
        self._permission_service = PermissionService(session_factory)
        self._audit_service = AuditService(session_factory)

    @staticmethod
    def _resolve_user(user: Optional[User] = None) -> User:
        actor = user if user is not None else get_current_user()
        if actor is None:
            raise EmployeeAdminManagementAccessDeniedError(
                "Authentication is required."
            )
        return actor

    def _require_admin(self, user: Optional[User] = None) -> User:
        actor = self._resolve_user(user)
        role = getattr(getattr(actor, "role", None), "name", None)
        if role != RoleDefinitions.ADMIN:
            raise EmployeeAdminManagementAccessDeniedError(
                "Administrator privileges are required for this action."
            )
        return actor

    @staticmethod
    def _reason(reason: Optional[str]) -> Optional[str]:
        if reason is None:
            return None
        value = str(reason).strip()
        return value or None

    def reopen_period(
        self,
        year: int,
        month: int,
        *,
        reason: Optional[str] = None,
        user: Optional[User] = None,
    ) -> EmployeeWorkRegistrationPeriod:
        """Reopen a CLOSED monthly period as an explicit Admin override."""
        actor = self._require_admin(user)
        reason = self._reason(reason)
        if not reason:
            raise EmployeeAdminManagementValidationError(
                "A reason is required when an administrator reopens a closed period."
            )

        with self._session_factory() as session:
            period = session.scalar(
                select(EmployeeWorkRegistrationPeriod).where(
                    EmployeeWorkRegistrationPeriod.year == year,
                    EmployeeWorkRegistrationPeriod.month == month,
                )
            )
            if period is None:
                raise EmployeeAdminManagementValidationError(
                    f"Registration period {month:02d}/{year} not found."
                )
            if period.status != EmployeeWorkRegistrationPeriod.STATUS_CLOSED:
                raise EmployeeAdminManagementValidationError(
                    "Only a CLOSED registration period can be reopened."
                )

            old_status = period.status
            period.status = EmployeeWorkRegistrationPeriod.STATUS_OPEN
            period.closed_at = None
            period.closed_by_user_id = None
            self._audit_service.record_in_session(
                session,
                self.ACTION_PERIOD_REOPENED,
                self.AUDIT_MODULE,
                target_type="EmployeeWorkRegistrationPeriod",
                target_id=period.id,
                target_name=f"{year:04d}-{month:02d}",
                details={
                    "year": year,
                    "month": month,
                    "old_status": old_status,
                    "new_status": period.status,
                    "reason": reason,
                },
                actor=actor,
            )
            session.commit()
            session.refresh(period)
            return period

    def delete_registration(
        self,
        registration_id: int,
        *,
        reason: Optional[str] = None,
        user: Optional[User] = None,
    ) -> None:
        """Delete one registration aggregate, including its availability blocks."""
        actor = self._require_admin(user)
        reason = self._reason(reason)
        if not reason:
            raise EmployeeAdminManagementValidationError(
                "A reason is required when an administrator deletes a registration."
            )

        with self._session_factory() as session:
            registration = EmployeeWorkRegistrationRepository(session).get(
                registration_id
            )
            if registration is None:
                raise EmployeeAdminManagementValidationError(
                    f"Registration {registration_id} not found."
                )

            employee_code = getattr(registration.employee, "employee_code", None)
            period = registration.period
            details = {
                "registration_id": registration.id,
                "employee_id": registration.employee_id,
                "period_id": registration.period_id,
                "period_status": getattr(period, "status", None),
                "registration_status": registration.status,
                "block_count": len(registration.blocks),
                "reason": reason,
            }
            session.delete(registration)
            self._audit_service.record_in_session(
                session,
                self.ACTION_REGISTRATION_DELETED,
                self.AUDIT_MODULE,
                target_type="EmployeeWorkRegistration",
                target_id=registration_id,
                target_name=employee_code,
                details=details,
                actor=actor,
            )
            session.commit()

    def delete_employee(
        self,
        employee_id: int,
        *,
        reason: Optional[str] = None,
        user: Optional[User] = None,
    ) -> None:
        """Hard-delete an employee only when no operational history exists.

        Employees with registrations, schedules, exceptions or working-time
        entries are retained so historical records cannot be destroyed by an
        accidental administrative delete.  Such employees should be archived
        through the existing Employee status lifecycle.
        """
        actor = self._require_admin(user)
        reason = self._reason(reason)
        if not reason:
            raise EmployeeAdminManagementValidationError(
                "A reason is required when an administrator deletes an employee."
            )

        with self._session_factory() as session:
            employee = EmployeeRepository(session).get_by_id(employee_id)
            if employee is None:
                raise EmployeeAdminManagementValidationError(
                    f"Employee {employee_id} not found."
                )

            history_counts = {
                "work_registrations": len(employee.work_registrations),
                "schedule_rules": len(employee.schedule_rules),
                "schedule_exceptions": len(employee.schedule_exceptions),
                "working_time_entries": len(employee.working_time_entries),
            }
            if any(history_counts.values()):
                raise EmployeeAdminManagementValidationError(
                    "Employee has operational history and cannot be hard-deleted. "
                    "Archive the employee instead."
                )

            employee_code = employee.employee_code
            user_id = employee.user_id
            session.delete(employee)
            self._audit_service.record_in_session(
                session,
                self.ACTION_EMPLOYEE_DELETED,
                self.AUDIT_MODULE,
                target_type="Employee",
                target_id=employee_id,
                target_name=employee_code,
                details={
                    "employee_id": employee_id,
                    "employee_code": employee_code,
                    "user_id": user_id,
                    "reason": reason,
                },
                actor=actor,
            )
            session.commit()
