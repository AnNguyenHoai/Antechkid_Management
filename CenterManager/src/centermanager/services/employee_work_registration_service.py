from __future__ import annotations
import logging
from datetime import date, time, timedelta
from typing import Optional
from centermanager.core.clock import get_clock
from centermanager.core.current_user import get_current_user
from centermanager.models.employee_work_registration import EmployeeWorkRegistration
from centermanager.models.employee_work_registration_period import EmployeeWorkRegistrationPeriod
from centermanager.repositories.provider import RepositoryProvider, create_default_repository_provider
from centermanager.services.permission_service import PermissionService
from centermanager.services.audit_service import AuditService
logger=logging.getLogger(__name__)
class EmployeeWorkRegistrationError(Exception): pass
class EmployeeWorkRegistrationAccessDeniedError(EmployeeWorkRegistrationError): pass
class EmployeeWorkRegistrationValidationError(EmployeeWorkRegistrationError): pass
class EmployeeWorkRegistrationService:
    SELF_PERMISSION="work_registration.self"; LEGACY_SELF_PERMISSION="working_time.registration.self"; ALL_PERMISSION="work_registration.view.all"; MANAGE_PERMISSION="work_registration.manage"; ADMIN_OVERRIDE_PERMISSION="work_registration.period.admin_override"
    AUDIT_MODULE="employee_work_registration"
    AUDIT_CREATED="WORK_REGISTRATION_CREATED"; AUDIT_UPDATED="WORK_REGISTRATION_UPDATED"; AUDIT_DELETED="WORK_REGISTRATION_DELETED"; AUDIT_SUBMITTED="WORK_REGISTRATION_SUBMITTED"; AUDIT_ACCEPTED="WORK_REGISTRATION_ACCEPTED"; AUDIT_REOPENED="WORK_REGISTRATION_REOPENED"; AUDIT_DEADLINE="WORK_REGISTRATION_DEADLINE_UPDATED"; AUDIT_CLOSED="WORK_REGISTRATION_PERIOD_CLOSED"
    def __init__(self,session_factory,repository_provider: Optional[RepositoryProvider]=None):
        self._sf=session_factory; self._repository_provider=repository_provider or create_default_repository_provider(); self._permission_service=PermissionService(session_factory); self._audit_service=AuditService(session_factory, repository_provider=self._repository_provider)
    def _user(self,user=None):
        u=user or get_current_user()
        if u is None: raise EmployeeWorkRegistrationAccessDeniedError("Authentication is required.")
        return u
    def _require_permission(self,p,u):
        if not self._permission_service.has_permission(p,u): raise EmployeeWorkRegistrationAccessDeniedError(f"Permission '{p}' is required.")
    def can_admin_override(self,user=None):
        u=self._user(user); return self._permission_service.has_permission(self.ADMIN_OVERRIDE_PERMISSION,u)
    def _scope(self,employee_id,user=None):
        u=self._user(user)
        with self._sf() as s:
            e=self._repository_provider.employees(s).get_by_id(employee_id)
            if not e: raise EmployeeWorkRegistrationValidationError("Employee not found.")
            if e.user_id==u.id:
                if not (self._permission_service.has_permission(self.SELF_PERMISSION,u) or self._permission_service.has_permission(self.LEGACY_SELF_PERMISSION,u)): raise EmployeeWorkRegistrationAccessDeniedError(f"Permission '{self.SELF_PERMISSION}' is required.")
            else:self._require_permission(self.ALL_PERMISSION,u)
            return e
    @staticmethod
    def week_start(value=None):
        d=value or get_clock().today()
        if not isinstance(d,date): raise EmployeeWorkRegistrationValidationError("Invalid registration week.")
        return d-timedelta(days=d.weekday())
    @classmethod
    def next_week(cls,today=None): return cls.week_start(today or get_clock().today())+timedelta(days=7)
    @classmethod
    def _week_range(cls,week_start):
        start=cls.week_start(week_start); return start,start+timedelta(days=6)
    def _period(self,s,week_start): return self._repository_provider.employee_work_registration_periods(s).get_or_create(self.week_start(week_start))
    def _open_period(self,s,week_start):
        p=self._period(s,week_start)
        if p.status!=EmployeeWorkRegistrationPeriod.STATUS_OPEN:raise EmployeeWorkRegistrationValidationError(f"Registration week {p.week_start:%d/%m/%Y} is closed.")
        today=get_clock().today()
        if p.submission_deadline and today>p.submission_deadline:raise EmployeeWorkRegistrationValidationError(f"Registration submission deadline was {p.submission_deadline:%d/%m/%Y}.")
        return p
    def get_period(self,week_start,user=None):
        u=self._user(user)
        with self._sf() as s: employee=self._repository_provider.employees(s).get_by_user_id(u.id)
        if not self._permission_service.has_permission(self.ALL_PERMISSION,u) and not (employee is not None and (self._permission_service.has_permission(self.SELF_PERMISSION,u) or self._permission_service.has_permission(self.LEGACY_SELF_PERMISSION,u))): self._require_permission(self.ALL_PERMISSION,u)
        with self._sf() as s:
            repo=self._repository_provider.employee_work_registration_periods(s); p=repo.get_or_create(self.week_start(week_start)); repo.detach(p); return p
    def list_for_employee(self,eid,week_start,user=None):
        self._scope(eid,user)
        with self._sf() as s:p=self._period(s,week_start);return self._repository_provider.employee_work_registrations(s).get_by_employee_period(eid,p.id)
    def list_all(self,week_start,user=None):
        u=self._user(user);self._require_permission(self.ALL_PERMISSION,u)
        with self._sf() as s:p=self._period(s,week_start);return self._repository_provider.employee_work_registrations(s).list_all(p.id)
    def _validate(self,d,start,end,typ,week_start=None):
        if not isinstance(d,date):raise EmployeeWorkRegistrationValidationError("Date is required.")
        if not isinstance(start,time) or not isinstance(end,time) or start>=end:raise EmployeeWorkRegistrationValidationError("End time must be after start time.")
        expected=self.week_start(week_start or self.next_week())
        if self.week_start(d)!=expected:raise EmployeeWorkRegistrationValidationError("Work registration date must be inside the selected registration week.")
        if not typ or len(typ.strip())>60:raise EmployeeWorkRegistrationValidationError("Work type is required and must be at most 60 characters.")
    @staticmethod
    def _overlap(blocks,work_date,start,end,exclude=None):
        for b in blocks:
            if exclude and b.id==exclude:continue
            if b.work_date==work_date and start<b.end_time and b.start_time<end:raise EmployeeWorkRegistrationValidationError("Registration overlaps an existing registration.")
    def _get_registration(self,s,eid,pid,create=False):
        repo=self._repository_provider.employee_work_registrations(s); r=repo.get_by_employee_period(eid,pid)
        if r is None and create:r=repo.create(eid,pid,EmployeeWorkRegistration.STATUS_DRAFT)
        return r
    def _audit(self,s,action,target,target_type="EmployeeWorkRegistration",details=None,actor=None,target_name=None): return self._audit_service.record_in_session(s,action,self.AUDIT_MODULE,target_type=target_type,target_id=getattr(target,"id",target),target_name=target_name,result="success",details=details,actor=actor)
    def create(self,eid,work_date,start_time,end_time,work_type="WORK",notes=None,user=None,week_start=None):
        u=self._user(user);self._scope(eid,u);ws=self.week_start(week_start or work_date);self._validate(work_date,start_time,end_time,work_type,ws)
        with self._sf() as s:
            repo=self._repository_provider.employee_work_registrations(s);repo.begin_write();p=self._open_period(s,ws);r=self._get_registration(s,eid,p.id,True);created=not bool(r.blocks)
            if r.status!=EmployeeWorkRegistration.STATUS_DRAFT:raise EmployeeWorkRegistrationValidationError("This registration week has already been submitted and cannot be changed.")
            self._overlap(r.blocks,work_date,start_time,end_time);repo.add_block(r.id,work_date,start_time,end_time,work_type.strip(),notes or None);self._audit(s,self.AUDIT_CREATED if created else self.AUDIT_UPDATED,r,details={"employee_id":eid,"week_start":ws.isoformat()},actor=u);s.commit();repo.refresh(r);return r
    def update(self,bid,*,work_date,start_time,end_time,work_type,notes=None,user=None):
        u=self._user(user);admin_override=self.can_admin_override(u)
        with self._sf() as s:
            repo=self._repository_provider.employee_work_registrations(s);repo.begin_write();b=repo.get_block(bid)
            if not b:raise EmployeeWorkRegistrationValidationError("Registration block not found.")
            r=b.registration;self._scope(r.employee_id,u);ws=r.period.week_start;self._validate(work_date,start_time,end_time,work_type,ws)
            if r.status!=EmployeeWorkRegistration.STATUS_DRAFT and not admin_override:raise EmployeeWorkRegistrationAccessDeniedError("Only draft registrations can be edited.")
            p=self._period(s,ws) if admin_override else self._open_period(s,ws);self._overlap(r.blocks,work_date,start_time,end_time,b.id);repo.update_block(bid,work_date,start_time,end_time,work_type.strip(),notes or None);self._audit(s,self.AUDIT_UPDATED,r,details={"operation":"update_block","block_id":bid,"admin_override":admin_override,"period_status":p.status},actor=u);s.commit();return r
    def delete(self,bid,user=None):
        u=self._user(user);admin_override=self.can_admin_override(u)
        with self._sf() as s:
            repo=self._repository_provider.employee_work_registrations(s);repo.begin_write();b=repo.get_block(bid)
            if not b:return
            r=b.registration;self._scope(r.employee_id,u)
            if r.status!=EmployeeWorkRegistration.STATUS_DRAFT and not admin_override:raise EmployeeWorkRegistrationAccessDeniedError("Only draft registrations can be deleted.")
            registration_id=r.id;repo.delete_block(bid);repo.flush();self._audit(s,self.AUDIT_DELETED,r,details={"block_id":bid,"registration_deleted":not bool(r.blocks),"admin_override":admin_override},actor=u)
            if not r.blocks:repo.delete(registration_id)
            s.commit()
    def submit(self,bid,user=None):raise EmployeeWorkRegistrationValidationError("Block-level submission is not supported. Submit the whole registration week.")
    def submit_week(self,eid,week_start,user=None):
        u=self._user(user);self._scope(eid,u);ws=self.week_start(week_start)
        if ws!=self.next_week():raise EmployeeWorkRegistrationValidationError("Only the next week can be submitted.")
        with self._sf() as s:
            repo=self._repository_provider.employee_work_registrations(s);repo.begin_write();p=self._open_period(s,ws);r=self._get_registration(s,eid,p.id)
            if not r or not r.blocks:raise EmployeeWorkRegistrationValidationError("Add at least one availability block before submitting.")
            if r.status!=EmployeeWorkRegistration.STATUS_DRAFT:raise EmployeeWorkRegistrationValidationError("Registration is not in draft state.")
            r.status=EmployeeWorkRegistration.STATUS_SUBMITTED;r.submitted_at=get_clock().now();self._audit(s,self.AUDIT_SUBMITTED,r,details={"employee_id":eid,"week_start":ws.isoformat(),"block_count":len(r.blocks)},actor=u);s.commit();return r
    def accept(self,eid,week_start,user=None):
        u=self._user(user);self._require_permission(self.MANAGE_PERMISSION,u);ws=self.week_start(week_start)
        with self._sf() as s:
            repo=self._repository_provider.employee_work_registrations(s);repo.begin_write();p=self._period(s,ws);r=self._get_registration(s,eid,p.id)
            if not r or r.status!=EmployeeWorkRegistration.STATUS_SUBMITTED:raise EmployeeWorkRegistrationValidationError("Only submitted registrations can be accepted.")
            r.status=EmployeeWorkRegistration.STATUS_ACCEPTED;r.accepted_at=get_clock().now();r.accepted_by_user_id=u.id;self._audit(s,self.AUDIT_ACCEPTED,r,details={"employee_id":eid,"week_start":ws.isoformat()},actor=u);s.commit();repo.refresh(r);return r
    def reopen(self,eid,week_start,user=None):
        u=self._user(user);self._require_permission(self.MANAGE_PERMISSION,u);ws=self.week_start(week_start)
        with self._sf() as s:
            repo=self._repository_provider.employee_work_registrations(s);repo.begin_write();p=self._period(s,ws);r=self._get_registration(s,eid,p.id)
            if not r or r.status!=EmployeeWorkRegistration.STATUS_ACCEPTED:raise EmployeeWorkRegistrationValidationError("Only accepted registrations can be reopened.")
            r.status=EmployeeWorkRegistration.STATUS_DRAFT;r.submitted_at=None;r.accepted_at=None;r.accepted_by_user_id=None;self._audit(s,self.AUDIT_REOPENED,r,details={"employee_id":eid,"week_start":ws.isoformat()},actor=u);s.commit();return r
    def set_submission_deadline(self,week_start,deadline:Optional[date],user=None):
        u=self._user(user);self._require_permission(self.MANAGE_PERMISSION,u);ws,end=self._week_range(week_start)
        if deadline is not None and not(ws<=deadline<=end):raise EmployeeWorkRegistrationValidationError("Submission deadline must be inside the registration week.")
        with self._sf() as s:
            repo=self._repository_provider.employee_work_registrations(s);repo.begin_write();p=self._period(s,ws)
            if p.status==EmployeeWorkRegistrationPeriod.STATUS_CLOSED:raise EmployeeWorkRegistrationValidationError("Registration period is already closed.")
            p.submission_deadline=deadline;self._audit(s,self.AUDIT_DEADLINE,p,target_type="EmployeeWorkRegistrationPeriod",details={"week_start":ws.isoformat(),"deadline":deadline.isoformat() if deadline else None},actor=u);s.commit();self._repository_provider.employee_work_registration_periods(s).refresh(p);return p
    def close_week(self,week_start,user=None):
        u=self._user(user);self._require_permission(self.MANAGE_PERMISSION,u);ws=self.week_start(week_start)
        with self._sf() as s:
            repo=self._repository_provider.employee_work_registrations(s);repo.begin_write();p=self._period(s,ws);rows=repo.list_all(p.id)
            if not rows:raise EmployeeWorkRegistrationValidationError("Cannot close a registration week with no employee submissions.")
            if any(r.status!=EmployeeWorkRegistration.STATUS_ACCEPTED for r in rows):raise EmployeeWorkRegistrationValidationError("All employee registrations must be accepted before closing the week.")
            p.status=EmployeeWorkRegistrationPeriod.STATUS_CLOSED;p.closed_at=get_clock().now();p.closed_by_user_id=u.id;self._audit(s,self.AUDIT_CLOSED,p,target_type="EmployeeWorkRegistrationPeriod",details={"week_start":ws.isoformat(),"registration_count":len(rows)},actor=u);s.commit();return len(rows)
