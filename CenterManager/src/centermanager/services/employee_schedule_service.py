from __future__ import annotations
from datetime import date, time
from typing import Optional
from centermanager.models.employee import Employee
from centermanager.models.employee_schedule import EmployeeScheduleRule, EmployeeScheduleException, VALID_EXCEPTION_TYPES
from centermanager.repositories.employee_repository import EmployeeRepository
from centermanager.repositories.employee_schedule_repository import EmployeeScheduleRepository
from centermanager.models.role import RoleDefinitions
from centermanager.core.current_user import get_current_user

class EmployeeScheduleError(Exception): pass
class EmployeeScheduleAccessDeniedError(EmployeeScheduleError): pass
class EmployeeScheduleValidationError(EmployeeScheduleError): pass

class EmployeeScheduleService:
    """Schedule business boundary. Management edits; employees read their own schedule."""
    def __init__(self, session_factory): self._sf = session_factory
    @staticmethod
    def _user(user=None):
        user = user or get_current_user()
        if user is None: raise EmployeeScheduleAccessDeniedError("Authentication is required.")
        return user
    @staticmethod
    def _management(user):
        return bool(user.role and user.role.name in {RoleDefinitions.ADMIN, RoleDefinitions.MANAGER})
    def can_view_all(self, user=None):
        u=self._user(user); return self._management(u) or u.has_permission("schedule.view.all")
    def can_view_self(self, user=None):
        u=self._user(user); return self.can_view_all(u) or u.has_permission("schedule.view.self")
    def _assert_scope(self, employee_id, user=None, write=False):
        u=self._user(user)
        with self._sf() as s:
            e=EmployeeRepository(s).get_by_id(employee_id)
            if not e: raise EmployeeScheduleValidationError(f"Employee {employee_id} not found.")
            if self._management(u):
                return e
            if e.user_id != u.id:
                raise EmployeeScheduleAccessDeniedError("You can only access your own schedule.")
            if write:
                raise EmployeeScheduleAccessDeniedError("Only administrators and managers can manage employee schedules.")
            if not self.can_view_self(u): raise EmployeeScheduleAccessDeniedError("Permission 'schedule.view.self' is required.")
            return e
    @staticmethod
    def _validate_rule(day_of_week, start_time, end_time, effective_from, effective_to):
        if day_of_week not in range(7): raise EmployeeScheduleValidationError("Day of week must be 0-6 (Monday-Sunday).")
        if not isinstance(start_time, time) or not isinstance(end_time, time) or start_time >= end_time: raise EmployeeScheduleValidationError("Schedule start time must be before end time.")
        if effective_to is not None and effective_to < effective_from: raise EmployeeScheduleValidationError("Effective end date must be on or after the start date.")
    @staticmethod
    def _date_ranges_overlap(a_from, a_to, b_from, b_to):
        return (a_to is None or b_from <= a_to) and (b_to is None or a_from <= b_to)
    @staticmethod
    def _times_overlap(a_start, a_end, b_start, b_end): return a_start < b_end and b_start < a_end
    def list_rules(self, employee_id, user=None):
        self._assert_scope(employee_id, user)
        with self._sf() as s: return EmployeeScheduleRepository(s).list_rules(employee_id)
    def list_exceptions(self, employee_id, user=None):
        self._assert_scope(employee_id, user)
        with self._sf() as s: return EmployeeScheduleRepository(s).list_exceptions(employee_id)
    def add_rule(self, employee_id, day_of_week, start_time, end_time, effective_from, effective_to=None, notes=None, user=None):
        self._assert_scope(employee_id, user, write=True)
        self._validate_rule(day_of_week,start_time,end_time,effective_from,effective_to)
        with self._sf() as s:
            repo=EmployeeScheduleRepository(s)
            for r in repo.list_rules(employee_id):
                if r.day_of_week == day_of_week and self._date_ranges_overlap(effective_from,effective_to,r.effective_from,r.effective_to) and self._times_overlap(start_time,end_time,r.start_time,r.end_time):
                    raise EmployeeScheduleValidationError("Schedule overlaps an existing rule for this employee.")
            r=EmployeeScheduleRule(employee_id=employee_id,day_of_week=day_of_week,start_time=start_time,end_time=end_time,effective_from=effective_from,effective_to=effective_to,notes=(notes or None))
            s.add(r); s.commit(); s.refresh(r); return r
    def update_rule(self, rule_id, *, day_of_week, start_time, end_time, effective_from, effective_to=None, notes=None, user=None):
        u=self._user(user)
        with self._sf() as s:
            repo=EmployeeScheduleRepository(s); r=repo.get_rule(rule_id)
            if not r: raise EmployeeScheduleValidationError(f"Schedule rule {rule_id} not found.")
            self._assert_scope(r.employee_id,u,write=True); self._validate_rule(day_of_week,start_time,end_time,effective_from,effective_to)
            for other in repo.list_rules(r.employee_id):
                if other.id != r.id and other.day_of_week == day_of_week and self._date_ranges_overlap(effective_from,effective_to,other.effective_from,other.effective_to) and self._times_overlap(start_time,end_time,other.start_time,other.end_time):
                    raise EmployeeScheduleValidationError("Schedule overlaps an existing rule for this employee.")
            r.day_of_week=day_of_week;r.start_time=start_time;r.end_time=end_time;r.effective_from=effective_from;r.effective_to=effective_to;r.notes=notes or None
            s.commit();s.refresh(r);return r
    def delete_rule(self, rule_id, user=None):
        u=self._user(user)
        with self._sf() as s:
            r=EmployeeScheduleRepository(s).get_rule(rule_id)
            if not r: return
            self._assert_scope(r.employee_id,u,write=True);s.delete(r);s.commit()
    def add_exception(self, employee_id, schedule_date, exception_type, start_time=None, end_time=None, notes=None, user=None):
        self._assert_scope(employee_id,user,write=True)
        typ=(exception_type or "").upper()
        if typ not in VALID_EXCEPTION_TYPES: raise EmployeeScheduleValidationError("Invalid schedule exception type.")
        if typ == "MODIFIED" and (not start_time or not end_time or start_time >= end_time): raise EmployeeScheduleValidationError("MODIFIED exception requires a valid start and end time.")
        if typ != "MODIFIED": start_time=end_time=None
        with self._sf() as s:
            repo=EmployeeScheduleRepository(s)
            if any(x.schedule_date == schedule_date for x in repo.list_exceptions(employee_id)): raise EmployeeScheduleValidationError("An exception already exists for this date.")
            x=EmployeeScheduleException(employee_id=employee_id,schedule_date=schedule_date,exception_type=typ,start_time=start_time,end_time=end_time,notes=notes or None)
            s.add(x);s.commit();s.refresh(x);return x
    def delete_exception(self, exception_id, user=None):
        u=self._user(user)
        with self._sf() as s:
            x=EmployeeScheduleRepository(s).get_exception(exception_id)
            if not x: return
            self._assert_scope(x.employee_id,u,write=True);s.delete(x);s.commit()
    def expected_for_date(self, employee_id, work_date: date, user=None):
        """Return the effective schedule blocks for a date, applying date exceptions."""
        self._assert_scope(employee_id,user)
        with self._sf() as s:
            repo=EmployeeScheduleRepository(s)
            exceptions=[x for x in repo.list_exceptions(employee_id) if x.schedule_date == work_date]
            if exceptions:
                x=exceptions[0]
                if x.exception_type in {"OFF","HOLIDAY","LEAVE"}: return []
                return [(x.start_time,x.end_time)] if x.start_time and x.end_time else []
            dow=work_date.weekday()
            return [(r.start_time,r.end_time) for r in repo.list_rules(employee_id) if r.day_of_week == dow and r.effective_from <= work_date and (r.effective_to is None or work_date <= r.effective_to)]
