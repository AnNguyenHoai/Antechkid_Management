from __future__ import annotations

import logging
from calendar import monthrange
from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import select

from centermanager.core.current_user import get_current_user
from centermanager.models.employee import Employee
from centermanager.models.employee_work_registration import EmployeeWorkRegistration
from centermanager.models.employee_work_registration_period import EmployeeWorkRegistrationPeriod
from centermanager.repositories.employee_repository import EmployeeRepository
from centermanager.repositories.employee_work_registration_repository import EmployeeWorkRegistrationRepository
from centermanager.services.permission_service import PermissionService

logger = logging.getLogger(__name__)


class EmployeeWorkRegistrationError(Exception):
    pass


class EmployeeWorkRegistrationAccessDeniedError(EmployeeWorkRegistrationError):
    pass


class EmployeeWorkRegistrationValidationError(EmployeeWorkRegistrationError):
    pass


class EmployeeWorkRegistrationService:
    """Monthly employee availability registration, separate from official schedule and attendance."""

    SELF_PERMISSION = "work_registration.self"
    LEGACY_SELF_PERMISSION = "working_time.registration.self"
    ALL_PERMISSION = "work_registration.view.all"
    MANAGE_PERMISSION = "work_registration.manage"

    def __init__(self, session_factory):
        self._sf = session_factory
        self._permission_service = PermissionService(session_factory)

    @staticmethod
    def _user(user=None):
        u = user or get_current_user()
        if u is None:
            raise EmployeeWorkRegistrationAccessDeniedError("Authentication is required.")
        return u

    def _has_permission(self, permission: str, user) -> bool:
        # Keep the same centralized RBAC policy used elsewhere: Admin is an
        # implicit superuser; every other role must receive the permission.
        return self._permission_service.has_permission(permission, user)

    def _require_permission(self, permission: str, user) -> None:
        if not self._has_permission(permission, user):
            raise EmployeeWorkRegistrationAccessDeniedError(
                f"Permission '{permission}' is required."
            )

    @staticmethod
    def next_month(today=None):
        d = today or date.today()
        return (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)

    def _scope(self, employee_id, user=None, write=False):
        """Authorize self/all access. ``write`` is intentionally not an authorization switch.

        The application WRITE/edit lease is UI/collaboration state. Business
        authorization is handled here through permissions and ownership.
        """
        u = self._user(user)
        with self._sf() as s:
            e = EmployeeRepository(s).get_by_id(employee_id)
            if not e:
                raise EmployeeWorkRegistrationValidationError("Employee not found.")

            if e.user_id == u.id:
                if not (
                    self._has_permission(self.SELF_PERMISSION, u)
                    or self._has_permission(self.LEGACY_SELF_PERMISSION, u)
                ):
                    raise EmployeeWorkRegistrationAccessDeniedError(
                        f"Permission '{self.SELF_PERMISSION}' is required."
                    )
                return e

            # Viewing another employee is a separate capability. A Manager is
            # not special merely because of its role name.
            self._require_permission(self.ALL_PERMISSION, u)
            return e

    @staticmethod
    def _month_range(year, month):
        try:
            start = date(year, month, 1)
            end = date(year, month, monthrange(year, month)[1])
        except ValueError as exc:
            raise EmployeeWorkRegistrationValidationError("Invalid registration month.") from exc
        return start, end

    def _get_or_create_period(self, session, year: int, month: int) -> EmployeeWorkRegistrationPeriod:
        start, _ = self._month_range(year, month)
        period = session.scalar(
            select(EmployeeWorkRegistrationPeriod).where(
                EmployeeWorkRegistrationPeriod.year == year,
                EmployeeWorkRegistrationPeriod.month == month,
            )
        )
        if period is None:
            period = EmployeeWorkRegistrationPeriod(year=year, month=month)
            session.add(period)
            session.flush()
        if period.status not in EmployeeWorkRegistrationPeriod.VALID_STATUSES:
            raise EmployeeWorkRegistrationValidationError("Registration period has an invalid status.")
        return period

    def get_period(self, year: int, month: int, user=None) -> EmployeeWorkRegistrationPeriod:
        u = self._user(user)
        # Period metadata is planning data; only managers/admins can inspect
        # arbitrary months. Employees may inspect their next-month period.
        if (year, month) != self.next_month():
            self._require_permission(self.ALL_PERMISSION, u)
        with self._sf() as s:
            period = self._get_or_create_period(s, year, month)
            s.expunge(period)
            return period

    def list_for_employee(self, employee_id, year, month, user=None):
        self._scope(employee_id, user)
        start, end = self._month_range(year, month)
        with self._sf() as s:
            return EmployeeWorkRegistrationRepository(s).list_for_employee(employee_id, start, end)

    def list_all(self, year, month, user=None):
        u = self._user(user)
        self._require_permission(self.ALL_PERMISSION, u)
        start, end = self._month_range(year, month)
        with self._sf() as s:
            return EmployeeWorkRegistrationRepository(s).list_all(start, end)

    def _validate_future_month(self, work_date):
        if self.next_month() != (work_date.year, work_date.month):
            raise EmployeeWorkRegistrationValidationError(
                "Work registration is only available for next month."
            )

    def _validate(self, work_date, start, end, work_type):
        if not isinstance(work_date, date):
            raise EmployeeWorkRegistrationValidationError("Date is required.")
        if not isinstance(start, time) or not isinstance(end, time) or start >= end:
            raise EmployeeWorkRegistrationValidationError("End time must be after start time.")
        self._validate_future_month(work_date)
        if not work_type or len(work_type.strip()) > 60:
            raise EmployeeWorkRegistrationValidationError(
                "Work type is required and must be at most 60 characters."
            )

    @staticmethod
    def _begin_write(session) -> None:
        """Serialize SQLite mutations before overlap/status checks.

        SQLite has no exclusion constraint for time ranges. BEGIN IMMEDIATE
        prevents two CenterManager instances from both passing the overlap
        check and then inserting conflicting blocks.
        """
        bind = session.get_bind()
        if bind.dialect.name == "sqlite":
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")

    @staticmethod
    def _overlap(repo, employee_id, day, start, end, exclude=None):
        for r in repo.list_for_employee(employee_id, day, day):
            if exclude and r.id == exclude:
                continue
            if r.status == EmployeeWorkRegistration.STATUS_CLOSED:
                continue
            if start < r.end_time and r.start_time < end:
                raise EmployeeWorkRegistrationValidationError(
                    "Registration overlaps an existing registration."
                )

    def _audit(self, action: str, registration=None, employee=None, user=None, details=None) -> None:
        try:
            from centermanager.services.audit_service import AuditService
            target = registration or employee
            target_type = "employee_work_registration" if registration is not None else "employee"
            target_id = getattr(target, "id", None)
            target_name = getattr(employee, "employee_code", None) or getattr(employee, "full_name", None)
            AuditService(self._sf).record(
                action,
                "employee",
                target_type,
                target_id,
                target_name,
                details=details,
                actor=user,
            )
        except Exception:
            logger.exception("Work registration audit failed: %s", action)

    def _ensure_open_period(self, session, year, month):
        period = self._get_or_create_period(session, year, month)
        if period.status != EmployeeWorkRegistrationPeriod.STATUS_OPEN:
            raise EmployeeWorkRegistrationValidationError(
                f"Registration period {month:02d}/{year} is closed."
            )
        if period.submission_deadline and date.today() > period.submission_deadline:
            raise EmployeeWorkRegistrationValidationError(
                f"Registration submission deadline was {period.submission_deadline.strftime('%d/%m/%Y')}."
            )
        return period

    def create(self, employee_id, work_date, start_time, end_time, work_type="WORK", notes=None, user=None):
        u = self._user(user)
        self._scope(employee_id, u, write=True)
        self._validate(work_date, start_time, end_time, work_type)
        with self._sf() as s:
            self._begin_write(s)
            period = self._ensure_open_period(s, work_date.year, work_date.month)
            repo = EmployeeWorkRegistrationRepository(s)
            existing = repo.list_for_employee(employee_id, work_date, work_date)
            if any(r.status in {EmployeeWorkRegistration.STATUS_SUBMITTED, EmployeeWorkRegistration.STATUS_CLOSED, EmployeeWorkRegistration.STATUS_APPROVED} for r in existing):
                raise EmployeeWorkRegistrationValidationError(
                    "This registration month has already been submitted and cannot be changed."
                )
            self._overlap(repo, employee_id, work_date, start_time, end_time)
            r = EmployeeWorkRegistration(
                employee_id=employee_id,
                period_id=period.id,
                work_date=work_date,
                start_time=start_time,
                end_time=end_time,
                work_type=work_type.strip(),
                status=EmployeeWorkRegistration.STATUS_DRAFT,
                notes=notes or None,
                created_by_user_id=u.id,
            )
            s.add(r)
            s.commit()
            s.refresh(r)
            self._audit("WORK_REGISTRATION_CREATED", r, user=u, details={"work_date": str(work_date), "start": str(start_time), "end": str(end_time)})
            return r

    def update(self, registration_id, *, work_date, start_time, end_time, work_type, notes=None, user=None):
        u = self._user(user)
        with self._sf() as s:
            self._begin_write(s)
            repo = EmployeeWorkRegistrationRepository(s)
            r = repo.get(registration_id)
            if not r:
                raise EmployeeWorkRegistrationValidationError("Registration not found.")
            employee_id = r.employee_id
            self._scope(employee_id, u, write=True)
            self._validate(work_date, start_time, end_time, work_type)
            if r.status != EmployeeWorkRegistration.STATUS_DRAFT:
                raise EmployeeWorkRegistrationAccessDeniedError("Only draft registrations can be edited.")
            period = self._ensure_open_period(s, work_date.year, work_date.month)
            if r.period_id and r.period_id != period.id:
                raise EmployeeWorkRegistrationValidationError("A registration cannot be moved to another month.")
            self._overlap(repo, employee_id, work_date, start_time, end_time, r.id)
            r.work_date = work_date
            r.start_time = start_time
            r.end_time = end_time
            r.work_type = work_type.strip()
            r.notes = notes or None
            r.period_id = period.id
            s.commit()
            s.refresh(r)
            self._audit("WORK_REGISTRATION_UPDATED", r, user=u, details={"work_date": str(work_date)})
            return r

    def delete(self, registration_id, user=None):
        u = self._user(user)
        with self._sf() as s:
            self._begin_write(s)
            r = EmployeeWorkRegistrationRepository(s).get(registration_id)
            if not r:
                return
            self._scope(r.employee_id, u, write=True)
            if r.status != EmployeeWorkRegistration.STATUS_DRAFT:
                raise EmployeeWorkRegistrationAccessDeniedError("Only draft registrations can be deleted.")
            employee_id = r.employee_id
            registration_id = r.id
            s.delete(r)
            s.commit()
            self._audit("WORK_REGISTRATION_DELETED", user=u, details={"registration_id": registration_id, "employee_id": employee_id})

    def submit(self, registration_id, user=None):
        """Deprecated block-level submit retained only for compatibility.

        New UI/business flows must use submit_month().
        """
        raise EmployeeWorkRegistrationValidationError(
            "Block-level submission is no longer supported. Submit the whole registration month."
        )

    def submit_month(self, employee_id, year, month, user=None):
        """Submit the employee's whole next-month availability atomically."""
        u = self._user(user)
        self._scope(employee_id, u, write=True)
        if (year, month) != self.next_month():
            raise EmployeeWorkRegistrationValidationError("Only the next month can be submitted.")
        start, end = self._month_range(year, month)
        with self._sf() as s:
            self._begin_write(s)
            period = self._ensure_open_period(s, year, month)
            rows = EmployeeWorkRegistrationRepository(s).list_for_employee(employee_id, start, end)
            if not rows:
                raise EmployeeWorkRegistrationValidationError(
                    "Add at least one availability block before submitting."
                )
            if any(r.status not in {EmployeeWorkRegistration.STATUS_DRAFT, EmployeeWorkRegistration.STATUS_SUBMITTED} for r in rows):
                raise EmployeeWorkRegistrationValidationError("Registration contains an invalid or closed block.")
            for r in rows:
                if r.status == EmployeeWorkRegistration.STATUS_DRAFT:
                    r.status = EmployeeWorkRegistration.STATUS_SUBMITTED
                    r.period_id = period.id
            s.commit()
            result = EmployeeWorkRegistrationRepository(s).list_for_employee(employee_id, start, end)
            self._audit("WORK_REGISTRATION_SUBMITTED", employee=rows[0].employee, user=u, details={"year": year, "month": month, "blocks": len(rows)})
            return result

    def set_submission_deadline(self, year, month, deadline: Optional[date], user=None):
        """Set/clear the submission deadline for a planning month."""
        u = self._user(user)
        self._require_permission(self.MANAGE_PERMISSION, u)
        start, end = self._month_range(year, month)
        if deadline is not None and not (start <= deadline <= end):
            raise EmployeeWorkRegistrationValidationError("Submission deadline must be inside the registration month.")
        with self._sf() as s:
            self._begin_write(s)
            period = self._get_or_create_period(s, year, month)
            if period.status == EmployeeWorkRegistrationPeriod.STATUS_CLOSED:
                raise EmployeeWorkRegistrationValidationError("Registration period is already closed.")
            period.submission_deadline = deadline
            s.commit()
            self._audit("WORK_REGISTRATION_DEADLINE_UPDATED", user=u, details={"year": year, "month": month, "deadline": str(deadline) if deadline else None})
            s.expunge(period)
            return period

    def close_month(self, year, month, user=None):
        """Close an entire registration period after all submitted entries are planned."""
        u = self._user(user)
        self._require_permission(self.MANAGE_PERMISSION, u)
        start, end = self._month_range(year, month)
        with self._sf() as s:
            self._begin_write(s)
            period = self._get_or_create_period(s, year, month)
            if period.status == EmployeeWorkRegistrationPeriod.STATUS_CLOSED:
                return 0
            rows = EmployeeWorkRegistrationRepository(s).list_all(start, end)
            if not rows:
                raise EmployeeWorkRegistrationValidationError(
                    "Cannot close a registration month with no employee submissions."
                )
            if any(r.status == EmployeeWorkRegistration.STATUS_DRAFT for r in rows):
                raise EmployeeWorkRegistrationValidationError(
                    "Cannot close the month while draft registrations remain."
                )
            for r in rows:
                if r.status == EmployeeWorkRegistration.STATUS_SUBMITTED:
                    r.status = EmployeeWorkRegistration.STATUS_CLOSED
            period.status = EmployeeWorkRegistrationPeriod.STATUS_CLOSED
            period.closed_at = datetime.now()
            period.closed_by_user_id = u.id
            s.commit()
            closed = sum(1 for r in rows if r.status == EmployeeWorkRegistration.STATUS_CLOSED)
            self._audit("WORK_REGISTRATION_PERIOD_CLOSED", user=u, details={"year": year, "month": month, "blocks": closed})
            return closed
