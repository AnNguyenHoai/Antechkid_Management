from __future__ import annotations
from calendar import monthrange
from datetime import date, time
from centermanager.core.current_user import get_current_user
from centermanager.models.employee import Employee
from centermanager.models.employee_work_registration import EmployeeWorkRegistration
from centermanager.models.role import RoleDefinitions
from centermanager.repositories.employee_repository import EmployeeRepository
from centermanager.repositories.employee_work_registration_repository import EmployeeWorkRegistrationRepository

class EmployeeWorkRegistrationError(Exception): pass
class EmployeeWorkRegistrationAccessDeniedError(EmployeeWorkRegistrationError): pass
class EmployeeWorkRegistrationValidationError(EmployeeWorkRegistrationError): pass

class EmployeeWorkRegistrationService:
    """Future-month availability registration. It is separate from actual attendance."""
    def __init__(self, session_factory): self._sf = session_factory
    @staticmethod
    def _user(user=None):
        u=user or get_current_user()
        if u is None: raise EmployeeWorkRegistrationAccessDeniedError("Authentication is required.")
        return u
    @staticmethod
    def _management(u): return bool(u.role and u.role.name in {RoleDefinitions.ADMIN, RoleDefinitions.MANAGER})
    @staticmethod
    def next_month(today=None):
        d=today or date.today()
        return (d.year+1,1) if d.month==12 else (d.year,d.month+1)
    def _scope(self, employee_id, user=None, write=False):
        u=self._user(user)
        with self._sf() as s:
            e=EmployeeRepository(s).get_by_id(employee_id)
            if not e: raise EmployeeWorkRegistrationValidationError("Employee not found.")
            if self._management(u): return e
            if e.user_id != u.id: raise EmployeeWorkRegistrationAccessDeniedError("You can only access your own work registration.")
            if not u.has_permission("working_time.registration.self") and not write:
                raise EmployeeWorkRegistrationAccessDeniedError("Permission 'working_time.registration.self' is required.")
            if write and not u.has_permission("working_time.registration.self"):
                raise EmployeeWorkRegistrationAccessDeniedError("Permission 'working_time.registration.self' is required.")
            return e
    def list_for_employee(self, employee_id, year, month, user=None):
        self._scope(employee_id,user)
        start=date(year,month,1); end=date(year,month,monthrange(year,month)[1])
        with self._sf() as s: return EmployeeWorkRegistrationRepository(s).list_for_employee(employee_id,start,end)
    def _validate_future_month(self, work_date):
        if self.next_month() != (work_date.year, work_date.month):
            raise EmployeeWorkRegistrationValidationError("Work registration is only available for next month.")
    def _validate(self, work_date, start, end, work_type):
        if not isinstance(work_date,date): raise EmployeeWorkRegistrationValidationError("Date is required.")
        if not isinstance(start,time) or not isinstance(end,time) or start >= end: raise EmployeeWorkRegistrationValidationError("End time must be after start time.")
        self._validate_future_month(work_date)
        if not work_type or len(work_type.strip())>60: raise EmployeeWorkRegistrationValidationError("Work type is required and must be at most 60 characters.")
    def _overlap(self, repo, employee_id, day, start, end, exclude=None):
        for r in repo.list_for_employee(employee_id,day,day):
            if exclude and r.id==exclude: continue
            if start < r.end_time and r.start_time < end: raise EmployeeWorkRegistrationValidationError("Registration overlaps an existing registration.")
    def create(self, employee_id, work_date, start_time, end_time, work_type="WORK", notes=None, user=None):
        u=self._user(user); self._scope(employee_id,u,write=True); self._validate(work_date,start_time,end_time,work_type)
        with self._sf() as s:
            repo=EmployeeWorkRegistrationRepository(s); self._overlap(repo,employee_id,work_date,start_time,end_time)
            r=EmployeeWorkRegistration(employee_id=employee_id,work_date=work_date,start_time=start_time,end_time=end_time,work_type=work_type.strip(),status=EmployeeWorkRegistration.STATUS_DRAFT,notes=notes or None,created_by_user_id=u.id)
            s.add(r);s.commit();s.refresh(r);return r
    def update(self, registration_id, *, work_date,start_time,end_time,work_type,notes=None,user=None):
        u=self._user(user)
        with self._sf() as s:
            repo=EmployeeWorkRegistrationRepository(s); r=repo.get(registration_id)
            if not r: raise EmployeeWorkRegistrationValidationError("Registration not found.")
            self._scope(r.employee_id,u,write=True); self._validate(work_date,start_time,end_time,work_type)
            if r.status != EmployeeWorkRegistration.STATUS_DRAFT: raise EmployeeWorkRegistrationAccessDeniedError("Only draft registrations can be edited.")
            self._overlap(repo,r.employee_id,work_date,start_time,end_time,r.id)
            r.work_date=work_date;r.start_time=start_time;r.end_time=end_time;r.work_type=work_type.strip();r.notes=notes or None
            s.commit();s.refresh(r);return r
    def delete(self, registration_id,user=None):
        u=self._user(user)
        with self._sf() as s:
            r=EmployeeWorkRegistrationRepository(s).get(registration_id)
            if not r:return
            self._scope(r.employee_id,u,write=True)
            if r.status != EmployeeWorkRegistration.STATUS_DRAFT: raise EmployeeWorkRegistrationAccessDeniedError("Only draft registrations can be deleted.")
            s.delete(r);s.commit()
    def submit(self, registration_id,user=None):
        u=self._user(user)
        with self._sf() as s:
            r=EmployeeWorkRegistrationRepository(s).get(registration_id)
            if not r: raise EmployeeWorkRegistrationValidationError("Registration not found.")
            self._scope(r.employee_id,u,write=True)
            if r.status != EmployeeWorkRegistration.STATUS_DRAFT: raise EmployeeWorkRegistrationValidationError("Only draft registrations can be submitted.")
            r.status=EmployeeWorkRegistration.STATUS_SUBMITTED;s.commit();s.refresh(r);return r
