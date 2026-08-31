from __future__ import annotations

import logging
from calendar import monthrange
from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import select

from centermanager.core.current_user import get_current_user
from centermanager.models.employee import Employee
from centermanager.models.employee_work_registration import EmployeeWorkRegistration, EmployeeWorkRegistrationBlock
from centermanager.models.employee_work_registration_period import EmployeeWorkRegistrationPeriod
from centermanager.repositories.employee_repository import EmployeeRepository
from centermanager.repositories.employee_work_registration_repository import EmployeeWorkRegistrationRepository
from centermanager.services.permission_service import PermissionService

logger = logging.getLogger(__name__)

class EmployeeWorkRegistrationError(Exception): pass
class EmployeeWorkRegistrationAccessDeniedError(EmployeeWorkRegistrationError): pass
class EmployeeWorkRegistrationValidationError(EmployeeWorkRegistrationError): pass

class EmployeeWorkRegistrationService:
    """Business service for one monthly employee availability aggregate."""
    SELF_PERMISSION = "work_registration.self"
    LEGACY_SELF_PERMISSION = "working_time.registration.self"
    ALL_PERMISSION = "work_registration.view.all"
    MANAGE_PERMISSION = "work_registration.manage"

    def __init__(self, session_factory):
        self._sf = session_factory
        self._permission_service = PermissionService(session_factory)

    def _user(self, user=None):
        u = user or get_current_user()
        if u is None: raise EmployeeWorkRegistrationAccessDeniedError("Authentication is required.")
        return u

    def _require_permission(self, permission, user):
        if not self._permission_service.has_permission(permission, user):
            raise EmployeeWorkRegistrationAccessDeniedError(f"Permission '{permission}' is required.")

    def _scope(self, employee_id, user=None):
        u = self._user(user)
        with self._sf() as s:
            e = EmployeeRepository(s).get_by_id(employee_id)
            if not e: raise EmployeeWorkRegistrationValidationError("Employee not found.")
            if e.user_id == u.id:
                if not (self._permission_service.has_permission(self.SELF_PERMISSION,u) or self._permission_service.has_permission(self.LEGACY_SELF_PERMISSION,u)):
                    raise EmployeeWorkRegistrationAccessDeniedError(f"Permission '{self.SELF_PERMISSION}' is required.")
            else:
                self._require_permission(self.ALL_PERMISSION,u)
            return e

    @staticmethod
    def next_month(today=None):
        d=today or date.today()
        return (d.year+1,1) if d.month==12 else (d.year,d.month+1)

    @staticmethod
    def _month_range(year, month):
        try: return date(year,month,1), date(year,month,monthrange(year,month)[1])
        except ValueError as exc: raise EmployeeWorkRegistrationValidationError("Invalid registration month.") from exc

    def _period(self, session, year, month):
        self._month_range(year,month)
        p=session.scalar(select(EmployeeWorkRegistrationPeriod).where(EmployeeWorkRegistrationPeriod.year==year, EmployeeWorkRegistrationPeriod.month==month))
        if p is None:
            p=EmployeeWorkRegistrationPeriod(year=year,month=month); session.add(p); session.flush()
        return p

    def _open_period(self, session, year, month):
        p=self._period(session,year,month)
        if p.status != EmployeeWorkRegistrationPeriod.STATUS_OPEN: raise EmployeeWorkRegistrationValidationError(f"Registration period {month:02d}/{year} is closed.")
        if p.submission_deadline and date.today()>p.submission_deadline: raise EmployeeWorkRegistrationValidationError(f"Registration submission deadline was {p.submission_deadline.strftime('%d/%m/%Y')}.")
        return p

    def get_period(self, year, month, user=None):
        u=self._user(user)
        if (year,month)!=self.next_month(): self._require_permission(self.ALL_PERMISSION,u)
        with self._sf() as s:
            p=self._period(s,year,month); s.expunge(p); return p

    def list_for_employee(self, employee_id, year, month, user=None):
        self._scope(employee_id,user)
        with self._sf() as s:
            p=self._period(s,year,month); return EmployeeWorkRegistrationRepository(s).get_by_employee_period(employee_id,p.id)

    def list_all(self, year, month, user=None):
        u=self._user(user); self._require_permission(self.ALL_PERMISSION,u)
        with self._sf() as s:
            p=self._period(s,year,month); return EmployeeWorkRegistrationRepository(s).list_all(p.id)

    @staticmethod
    def _validate_block(work_date,start,end,work_type):
        if not isinstance(work_date,date): raise EmployeeWorkRegistrationValidationError("Date is required.")
        if not isinstance(start,time) or not isinstance(end,time) or start>=end: raise EmployeeWorkRegistrationValidationError("End time must be after start time.")
        if not work_type or len(work_type.strip())>60: raise EmployeeWorkRegistrationValidationError("Work type is required and must be at most 60 characters.")

    def _ensure_next_month(self, work_date):
        if (work_date.year,work_date.month)!=self.next_month(): raise EmployeeWorkRegistrationValidationError("Work registration is only available for next month.")

    @staticmethod
    def _begin_write(session):
        if session.get_bind().dialect.name=="sqlite": session.connection().exec_driver_sql("BEGIN IMMEDIATE")

    @staticmethod
    def _overlap(blocks,start,end,exclude=None):
        for b in blocks:
            if exclude and b.id==exclude: continue
            if start < b.end_time and b.start_time < end: raise EmployeeWorkRegistrationValidationError("Registration overlaps an existing registration.")

    def _audit(self, action, registration=None, employee=None, user=None, details=None):
        try:
            from centermanager.services.audit_service import AuditService
            target=registration or employee
            AuditService(self._sf).record(action,"employee","employee_work_registration" if registration else "employee",getattr(target,"id",None),getattr(employee,"employee_code",None),details=details,actor=user)
        except Exception: logger.exception("Work registration audit failed: %s",action)

    def _get_registration(self, session, employee_id, period_id, create=False):
        repo=EmployeeWorkRegistrationRepository(session); r=repo.get_by_employee_period(employee_id,period_id)
        if r is None and create:
            r=EmployeeWorkRegistration(employee_id=employee_id,period_id=period_id,status=EmployeeWorkRegistration.STATUS_DRAFT); session.add(r); session.flush()
        return r

    def create(self, employee_id, work_date, start_time, end_time, work_type="WORK", notes=None, user=None):
        u=self._user(user); self._scope(employee_id,u); self._ensure_next_month(work_date); self._validate_block(work_date,start_time,end_time,work_type)
        with self._sf() as s:
            self._begin_write(s); p=self._open_period(s,work_date.year,work_date.month); r=self._get_registration(s,employee_id,p.id,True)
            if r.status != EmployeeWorkRegistration.STATUS_DRAFT: raise EmployeeWorkRegistrationValidationError("This registration month has already been submitted and cannot be changed.")
            self._overlap(r.blocks,start_time,end_time)
            r.blocks.append(EmployeeWorkRegistrationBlock(work_date=work_date,start_time=start_time,end_time=end_time,work_type=work_type.strip(),notes=notes or None))
            s.commit(); s.refresh(r); self._audit("WORK_REGISTRATION_BLOCK_CREATED",r,user=u,details={"work_date":str(work_date)}); return r

    def update(self, registration_id, *, work_date, start_time, end_time, work_type, notes=None, user=None):
        u=self._user(user)
        with self._sf() as s:
            self._begin_write(s); repo=EmployeeWorkRegistrationRepository(s); b=repo.get_block(registration_id)
            if not b: raise EmployeeWorkRegistrationValidationError("Registration block not found.")
            r=b.registration; self._scope(r.employee_id,u); self._ensure_next_month(work_date); self._validate_block(work_date,start_time,end_time,work_type)
            if r.status!=EmployeeWorkRegistration.STATUS_DRAFT: raise EmployeeWorkRegistrationAccessDeniedError("Only draft registrations can be edited.")
            self._open_period(s,work_date.year,work_date.month); self._overlap(r.blocks,start_time,end_time,b.id)
            b.work_date,b.start_time,b.end_time,b.work_type,b.notes=work_date,start_time,end_time,work_type.strip(),notes or None
            s.commit(); s.refresh(r); return r

    def delete(self, registration_id, user=None):
        u=self._user(user)
        with self._sf() as s:
            self._begin_write(s); b=EmployeeWorkRegistrationRepository(s).get_block(registration_id)
            if not b:return
            r=b.registration; self._scope(r.employee_id,u)
            if r.status!=EmployeeWorkRegistration.STATUS_DRAFT: raise EmployeeWorkRegistrationAccessDeniedError("Only draft registrations can be deleted.")
            s.delete(b)
            if len(r.blocks)==1: s.delete(r)
            s.commit()

    def submit(self, registration_id,user=None): raise EmployeeWorkRegistrationValidationError("Block-level submission is no longer supported. Submit the whole registration month.")

    def submit_month(self, employee_id, year, month, user=None):
        u=self._user(user); self._scope(employee_id,u)
        if (year,month)!=self.next_month(): raise EmployeeWorkRegistrationValidationError("Only the next month can be submitted.")
        with self._sf() as s:
            self._begin_write(s); p=self._open_period(s,year,month); r=self._get_registration(s,employee_id,p.id)
            if not r or not r.blocks: raise EmployeeWorkRegistrationValidationError("Add at least one availability block before submitting.")
            if r.status not in (EmployeeWorkRegistration.STATUS_DRAFT,EmployeeWorkRegistration.STATUS_SUBMITTED): raise EmployeeWorkRegistrationValidationError("Registration is already accepted or unavailable for submission.")
            r.status=EmployeeWorkRegistration.STATUS_SUBMITTED; r.submitted_at=datetime.now(); s.commit(); s.refresh(r); self._audit("WORK_REGISTRATION_SUBMITTED",r,user=u,details={"year":year,"month":month,"blocks":len(r.blocks)}); return r

    def accept(self, employee_id, year, month, user=None):
        u=self._user(user); self._require_permission(self.MANAGE_PERMISSION,u)
        with self._sf() as s:
            p=self._period(s,year,month); r=self._get_registration(s,employee_id,p.id)
            if not r or r.status!=EmployeeWorkRegistration.STATUS_SUBMITTED: raise EmployeeWorkRegistrationValidationError("Only submitted registrations can be accepted.")
            r.status=EmployeeWorkRegistration.STATUS_ACCEPTED; r.accepted_at=datetime.now(); r.accepted_by_user_id=u.id; s.commit(); s.refresh(r); self._audit("WORK_REGISTRATION_ACCEPTED",r,user=u,details={"year":year,"month":month}); return r

    def reopen(self, employee_id, year, month, user=None):
        u=self._user(user); self._require_permission(self.MANAGE_PERMISSION,u)
        with self._sf() as s:
            p=self._period(s,year,month); r=self._get_registration(s,employee_id,p.id)
            if not r or r.status!=EmployeeWorkRegistration.STATUS_ACCEPTED: raise EmployeeWorkRegistrationValidationError("Only accepted registrations can be reopened.")
            r.status=EmployeeWorkRegistration.STATUS_SUBMITTED; r.accepted_at=None; r.accepted_by_user_id=None; s.commit(); s.refresh(r); return r

    def set_submission_deadline(self,year,month,deadline:Optional[date],user=None):
        u=self._user(user); self._require_permission(self.MANAGE_PERMISSION,u); start,end=self._month_range(year,month)
        if deadline is not None and not(start<=deadline<=end): raise EmployeeWorkRegistrationValidationError("Submission deadline must be inside the registration month.")
        with self._sf() as s:
            self._begin_write(s); p=self._period(s,year,month)
            if p.status==EmployeeWorkRegistrationPeriod.STATUS_CLOSED: raise EmployeeWorkRegistrationValidationError("Registration period is already closed.")
            p.submission_deadline=deadline; s.commit(); s.refresh(p); return p

    def close_month(self,year,month,user=None):
        u=self._user(user); self._require_permission(self.MANAGE_PERMISSION,u)
        with self._sf() as s:
            self._begin_write(s); p=self._period(s,year,month); rows=EmployeeWorkRegistrationRepository(s).list_all(p.id)
            if not rows: raise EmployeeWorkRegistrationValidationError("Cannot close a registration month with no employee submissions.")
            if any(r.status==EmployeeWorkRegistration.STATUS_DRAFT for r in rows): raise EmployeeWorkRegistrationValidationError("Cannot close the month while draft registrations remain.")
            for r in rows:
                if r.status==EmployeeWorkRegistration.STATUS_SUBMITTED: r.status=EmployeeWorkRegistration.STATUS_ACCEPTED; r.accepted_at=datetime.now(); r.accepted_by_user_id=u.id
            p.status=EmployeeWorkRegistrationPeriod.STATUS_CLOSED; p.closed_at=datetime.now(); p.closed_by_user_id=u.id; s.commit(); return len(rows)
