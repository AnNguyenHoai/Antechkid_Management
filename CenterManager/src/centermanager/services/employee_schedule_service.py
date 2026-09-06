from __future__ import annotations
from datetime import date, time
from typing import Optional
from centermanager.models.employee import Employee
from centermanager.models.employee_schedule import EmployeeScheduleRule, EmployeeScheduleException, VALID_EXCEPTION_TYPES
from centermanager.repositories.employee_repository import EmployeeRepository
from centermanager.repositories.employee_schedule_repository import EmployeeScheduleRepository
from centermanager.core.current_user import get_current_user
from centermanager.models.role import RoleDefinitions
from centermanager.services.employee_capability_policy import EmployeeCapabilityPolicy

class EmployeeScheduleError(Exception): pass
class EmployeeScheduleAccessDeniedError(EmployeeScheduleError): pass
class EmployeeScheduleValidationError(EmployeeScheduleError): pass

class EmployeeScheduleService:
    """Schedule business boundary using explicit operation capabilities."""
    VIEW_SELF = "schedule.view.self"
    VIEW_ALL = "schedule.view.all"
    MANAGE = "schedule.manage"

    def __init__(self, session_factory): self._sf = session_factory
    @staticmethod
    def _user(user=None):
        user = user or get_current_user()
        if user is None: raise EmployeeScheduleAccessDeniedError("Authentication is required.")
        return user
    def _has(self, user, capability): return EmployeeCapabilityPolicy.has(user, capability)
    def can_view_all(self, user=None):
        u=self._user(user); return self._has(u,self.VIEW_ALL)
    def can_view_self(self, user=None): u=self._user(user); return self._has(u,self.VIEW_SELF) or self.can_view_all(u)
    def _assert_scope(self, employee_id, user=None, write=False):
        u=self._user(user)
        with self._sf() as s:
            e=EmployeeRepository(s).get_by_id(employee_id)
            if not e: raise EmployeeScheduleValidationError(f"Employee {employee_id} not found.")
            is_self=e.user_id==u.id
            if write:
                if not self._has(u,self.MANAGE): raise EmployeeScheduleAccessDeniedError(f"Permission '{self.MANAGE}' is required.")
                return e
            if self._has(u,self.VIEW_ALL): return e
            if is_self and self._has(u,self.VIEW_SELF): return e
            raise EmployeeScheduleAccessDeniedError("You can only access your own schedule.")
    def expected_for_date(self, employee_id, work_date: date, user=None):
        self._assert_scope(employee_id,user)
        with self._sf() as s:
            repo=EmployeeScheduleRepository(s)
            exceptions=[x for x in repo.list_exceptions(employee_id) if x.schedule_date==work_date]
            if exceptions:
                x=exceptions[0]
                if x.exception_type in {"OFF","HOLIDAY","LEAVE"}: return []
                return [(x.start_time,x.end_time)] if x.start_time and x.end_time else []
            dow=work_date.weekday()
            return [(r.start_time,r.end_time) for r in repo.list_rules(employee_id) if r.day_of_week==dow and r.effective_from<=work_date and (r.effective_to is None or work_date<=r.effective_to)]
