from __future__ import annotations
import logging
from calendar import monthrange
from datetime import date, time
from typing import Optional
from sqlalchemy import select
from centermanager.core.clock import get_clock
from centermanager.core.current_user import get_current_user
from centermanager.models.employee import Employee
from centermanager.models.employee_work_registration import EmployeeWorkRegistration, EmployeeWorkRegistrationBlock
from centermanager.models.employee_work_registration_period import EmployeeWorkRegistrationPeriod
from centermanager.repositories.employee_repository import EmployeeRepository
from centermanager.repositories.employee_work_registration_repository import EmployeeWorkRegistrationRepository
from centermanager.services.permission_service import PermissionService
logger=logging.getLogger(__name__)
class EmployeeWorkRegistrationError(Exception): pass
class EmployeeWorkRegistrationAccessDeniedError(EmployeeWorkRegistrationError): pass
class EmployeeWorkRegistrationValidationError(EmployeeWorkRegistrationError): pass
class EmployeeWorkRegistrationService:
    SELF_PERMISSION="work_registration.self"; LEGACY_SELF_PERMISSION="working_time.registration.self"; ALL_PERMISSION="work_registration.view.all"; MANAGE_PERMISSION="work_registration.manage"
    def __init__(self,session_factory): self._sf=session_factory; self._permission_service=PermissionService(session_factory)
    def _user(self,user=None):
        u=user or get_current_user()
        if u is None: raise EmployeeWorkRegistrationAccessDeniedError("Authentication is required.")
        return u
    def _require_permission(self,p,u):
        if not self._permission_service.has_permission(p,u): raise EmployeeWorkRegistrationAccessDeniedError(f"Permission '{p}' is required.")
    def _scope(self,employee_id,user=None):
        u=self._user(user)
        with self._sf() as s:
            e=EmployeeRepository(s).get_by_id(employee_id)
            if not e: raise EmployeeWorkRegistrationValidationError("Employee not found.")
            if e.user_id==u.id:
                if not(self._permission_service.has_permission(self.SELF_PERMISSION,u) or self._permission_service.has_permission(self.LEGACY_SELF_PERMISSION,u)): raise EmployeeWorkRegistrationAccessDeniedError(f"Permission '{self.SELF_PERMISSION}' is required.")
            else:self._require_permission(self.ALL_PERMISSION,u)
            return e
    @staticmethod
    def next_month(today=None):
        d=today or get_clock().today(); return (d.year+1,1) if d.month==12 else (d.year,d.month+1)
    @staticmethod
    def _month_range(y,m):
        try:return date(y,m,1),date(y,m,monthrange(y,m)[1])
        except ValueError as exc:raise EmployeeWorkRegistrationValidationError("Invalid registration month.") from exc
    def _period(self,s,y,m):
        self._month_range(y,m); p=s.scalar(select(EmployeeWorkRegistrationPeriod).where(EmployeeWorkRegistrationPeriod.year==y,EmployeeWorkRegistrationPeriod.month==m))
        if p is None:p=EmployeeWorkRegistrationPeriod(year=y,month=m);s.add(p);s.flush()
        return p
    def _open_period(self,s,y,m):
        p=self._period(s,y,m)
        if p.status!=EmployeeWorkRegistrationPeriod.STATUS_OPEN:raise EmployeeWorkRegistrationValidationError(f"Registration period {m:02d}/{y} is closed.")
        today=get_clock().today()
        if p.submission_deadline and today>p.submission_deadline:raise EmployeeWorkRegistrationValidationError(f"Registration submission deadline was {p.submission_deadline.strftime('%d/%m/%Y')}.")
        return p
    def get_period(self,y,m,user=None):
        u=self._user(user)
        if (y,m)!=self.next_month():self._require_permission(self.ALL_PERMISSION,u)
        with self._sf() as s:p=self._period(s,y,m);s.expunge(p);return p
    def list_for_employee(self,eid,y,m,user=None):
        self._scope(eid,user)
        with self._sf() as s:p=self._period(s,y,m);return EmployeeWorkRegistrationRepository(s).get_by_employee_period(eid,p.id)
    def list_all(self,y,m,user=None):
        u=self._user(user);self._require_permission(self.ALL_PERMISSION,u)
        with self._sf() as s:p=self._period(s,y,m);return EmployeeWorkRegistrationRepository(s).list_all(p.id)
    def _validate(self,d,start,end,typ):
        if not isinstance(d,date):raise EmployeeWorkRegistrationValidationError("Date is required.")
        if not isinstance(start,time) or not isinstance(end,time) or start>=end:raise EmployeeWorkRegistrationValidationError("End time must be after start time.")
        if self.next_month()!=(d.year,d.month):raise EmployeeWorkRegistrationValidationError("Work registration is only available for next month.")
        if not typ or len(typ.strip())>60:raise EmployeeWorkRegistrationValidationError("Work type is required and must be at most 60 characters.")
    @staticmethod
    def _begin_write(s):
        if s.get_bind().dialect.name=="sqlite":s.connection().exec_driver_sql("BEGIN IMMEDIATE")
    @staticmethod
    def _overlap(blocks,work_date,start,end,exclude=None):
        for b in blocks:
            if exclude and b.id==exclude:continue
            if b.work_date != work_date:continue
            if start<b.end_time and b.start_time<end:raise EmployeeWorkRegistrationValidationError("Registration overlaps an existing registration.")
    def _get_registration(self,s,eid,pid,create=False):
        r=EmployeeWorkRegistrationRepository(s).get_by_employee_period(eid,pid)
        if r is None and create:r=EmployeeWorkRegistration(employee_id=eid,period_id=pid,status=EmployeeWorkRegistration.STATUS_DRAFT);s.add(r);s.flush()
        return r
    def create(self,eid,work_date,start_time,end_time,work_type="WORK",notes=None,user=None):
        u=self._user(user);self._scope(eid,u);self._validate(work_date,start_time,end_time,work_type)
        with self._sf() as s:
            self._begin_write(s);p=self._open_period(s,work_date.year,work_date.month);r=self._get_registration(s,eid,p.id,True)
            if r.status!=EmployeeWorkRegistration.STATUS_DRAFT:raise EmployeeWorkRegistrationValidationError("This registration month has already been submitted and cannot be changed.")
            self._overlap(r.blocks,work_date,start_time,end_time);r.blocks.append(EmployeeWorkRegistrationBlock(work_date=work_date,start_time=start_time,end_time=end_time,work_type=work_type.strip(),notes=notes or None));s.commit();s.refresh(r);return r
    def update(self,bid,*,work_date,start_time,end_time,work_type,notes=None,user=None):
        u=self._user(user)
        with self._sf() as s:
            self._begin_write(s);b=EmployeeWorkRegistrationRepository(s).get_block(bid)
            if not b:raise EmployeeWorkRegistrationValidationError("Registration block not found.")
            r=b.registration;self._scope(r.employee_id,u);self._validate(work_date,start_time,end_time,work_type)
            if r.status!=EmployeeWorkRegistration.STATUS_DRAFT:raise EmployeeWorkRegistrationAccessDeniedError("Only draft registrations can be edited.")
            self._open_period(s,work_date.year,work_date.month);self._overlap(r.blocks,work_date,start_time,end_time,b.id);b.work_date,b.start_time,b.end_time,b.work_type,b.notes=work_date,start_time,end_time,work_type.strip(),notes or None;s.commit();return r
    def delete(self,bid,user=None):
        u=self._user(user)
        with self._sf() as s:
            self._begin_write(s);b=EmployeeWorkRegistrationRepository(s).get_block(bid)
            if not b:return
            r=b.registration;self._scope(r.employee_id,u)
            if r.status!=EmployeeWorkRegistration.STATUS_DRAFT:raise EmployeeWorkRegistrationAccessDeniedError("Only draft registrations can be deleted.")
            s.delete(b);s.flush()
            if not r.blocks:s.delete(r)
            s.commit()
    def submit(self,bid,user=None):raise EmployeeWorkRegistrationValidationError("Block-level submission is no longer supported. Submit the whole registration month.")
    def submit_month(self,eid,y,m,user=None):
        u=self._user(user);self._scope(eid,u)
        if (y,m)!=self.next_month():raise EmployeeWorkRegistrationValidationError("Only the next month can be submitted.")
        with self._sf() as s:
            self._begin_write(s);p=self._open_period(s,y,m);r=self._get_registration(s,eid,p.id)
            if not r or not r.blocks:raise EmployeeWorkRegistrationValidationError("Add at least one availability block before submitting.")
            if r.status!=EmployeeWorkRegistration.STATUS_DRAFT:raise EmployeeWorkRegistrationValidationError("Registration is not in draft state.")
            r.status=EmployeeWorkRegistration.STATUS_SUBMITTED;r.submitted_at=get_clock().now();s.commit();return r
    def accept(self,eid,y,m,user=None):
        u=self._user(user);self._require_permission(self.MANAGE_PERMISSION,u)
        with self._sf() as s:
            p=self._period(s,y,m);r=self._get_registration(s,eid,p.id)
            if not r or r.status!=EmployeeWorkRegistration.STATUS_SUBMITTED:raise EmployeeWorkRegistrationValidationError("Only submitted registrations can be accepted.")
            r.status=EmployeeWorkRegistration.STATUS_ACCEPTED;r.accepted_at=get_clock().now();r.accepted_by_user_id=u.id;s.commit();return r
    def reopen(self,eid,y,m,user=None):
        u=self._user(user);self._require_permission(self.MANAGE_PERMISSION,u)
        with self._sf() as s:
            p=self._period(s,y,m);r=self._get_registration(s,eid,p.id)
            if not r or r.status!=EmployeeWorkRegistration.STATUS_ACCEPTED:raise EmployeeWorkRegistrationValidationError("Only accepted registrations can be reopened.")
            r.status=EmployeeWorkRegistration.STATUS_DRAFT;r.submitted_at=None;r.accepted_at=None;r.accepted_by_user_id=None;s.commit();return r
    def set_submission_deadline(self,y,m,deadline:Optional[date],user=None):
        u=self._user(user);self._require_permission(self.MANAGE_PERMISSION,u);start,end=self._month_range(y,m)
        if deadline is not None and not(start<=deadline<=end):raise EmployeeWorkRegistrationValidationError("Submission deadline must be inside the registration month.")
        with self._sf() as s:
            self._begin_write(s);p=self._period(s,y,m)
            if p.status==EmployeeWorkRegistrationPeriod.STATUS_CLOSED:raise EmployeeWorkRegistrationValidationError("Registration period is already closed.")
            p.submission_deadline=deadline;s.commit();s.refresh(p);return p
    def close_month(self,y,m,user=None):
        u=self._user(user);self._require_permission(self.MANAGE_PERMISSION,u)
        with self._sf() as s:
            self._begin_write(s);p=self._period(s,y,m);rows=EmployeeWorkRegistrationRepository(s).list_all(p.id)
            if not rows:raise EmployeeWorkRegistrationValidationError("Cannot close a registration month with no employee submissions.")
            if any(r.status!=EmployeeWorkRegistration.STATUS_ACCEPTED for r in rows):raise EmployeeWorkRegistrationValidationError("All employee registrations must be accepted before closing the month.")
            p.status=EmployeeWorkRegistrationPeriod.STATUS_CLOSED;p.closed_at=get_clock().now();p.closed_by_user_id=u.id;s.commit();return len(rows)
