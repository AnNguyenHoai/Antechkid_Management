from __future__ import annotations
from datetime import date, datetime, time, timedelta
from centermanager.core.current_user import get_current_user
from centermanager.models.employee import Employee
from centermanager.models.employee_working_time import EmployeeWorkingTimeEntry
from centermanager.repositories.employee_repository import EmployeeRepository
from centermanager.repositories.employee_working_time_repository import EmployeeWorkingTimeRepository
from centermanager.services.employee_capability_policy import EmployeeCapabilityPolicy


class EmployeeWorkingTimeError(Exception): pass
class EmployeeWorkingTimeAccessDeniedError(EmployeeWorkingTimeError): pass
class EmployeeWorkingTimeValidationError(EmployeeWorkingTimeError): pass


class EmployeeWorkingTimeService:
    """Actual working-time boundary using explicit operation capabilities."""
    VIEW_SELF = "working_time.view.self"
    VIEW_ALL = "working_time.view.all"
    CREATE_SELF = "working_time.create.self"
    MANAGE = "working_time.manage"
    LOCK = "working_time.lock"

    def __init__(self, session_factory, schedule_service=None):
        self._sf = session_factory
        self._schedule = schedule_service

    @staticmethod
    def _user(user=None):
        u = user or get_current_user()
        if u is None: raise EmployeeWorkingTimeAccessDeniedError("Authentication is required.")
        return u

    @staticmethod
    def _has(user, capability):
        return EmployeeCapabilityPolicy.has(user, capability)

    def can_view_all(self, user=None):
        u=self._user(user); return self._has(u,self.VIEW_ALL)

    def can_view_self(self, user=None):
        u=self._user(user); return self._has(u,self.VIEW_SELF) or self.can_view_all(u)

    def _scope(self, employee_id, user=None, write=False):
        u=self._user(user)
        with self._sf() as s:
            e=EmployeeRepository(s).get_by_id(employee_id)
            if not e: raise EmployeeWorkingTimeValidationError(f"Employee {employee_id} not found.")
            is_self = e.user_id == u.id
            if write:
                if self._has(u,self.MANAGE):
                    return e
                if is_self and self._has(u,self.CREATE_SELF):
                    return e
                raise EmployeeWorkingTimeAccessDeniedError(
                    f"Permission '{self.CREATE_SELF if is_self else self.MANAGE}' is required."
                )
            if self._has(u,self.VIEW_ALL):
                return e
            if is_self and self._has(u,self.VIEW_SELF):
                return e
            raise EmployeeWorkingTimeAccessDeniedError("You can only access your own working time.")

    @staticmethod
    def _validate_times(start_time, end_time):
        if not isinstance(start_time, time): raise EmployeeWorkingTimeValidationError("Start time is required.")
        if end_time is not None and start_time >= end_time: raise EmployeeWorkingTimeValidationError("End time must be after start time.")

    @staticmethod
    def _minutes(start, end):
        if not end:
            return 0
        return int((datetime.combine(date.min, end) - datetime.combine(date.min, start)).total_seconds() / 60)

    def _assert_write_scope(self, employee_id, user=None):
        u = self._user(user)
        return self._scope(employee_id, u, write=True)

    def _assert_no_overlap(self, repo, employee_id, work_date, start, end, exclude_id=None):
        if end is None: return
        for e in repo.list_for_employee(employee_id, work_date, work_date):
            if exclude_id and e.id == exclude_id: continue
            if e.end_time is None: raise EmployeeWorkingTimeValidationError("An open working-time entry already exists for this employee.")
            if start < e.end_time and e.start_time < end:
                raise EmployeeWorkingTimeValidationError("Working-time entry overlaps an existing entry.")

    def list_entries(self, employee_id, start_date=None, end_date=None, user=None):
        self._scope(employee_id,user)
        with self._sf() as s: return EmployeeWorkingTimeRepository(s).list_for_employee(employee_id,start_date,end_date)

    def create_booking(self, employee_id, work_date, start_time, end_time, work_type="WORK", notes=None, user=None):
        u=self._user(user); self._assert_write_scope(employee_id,u); self._validate_times(start_time,end_time)
        if not isinstance(work_date,date): raise EmployeeWorkingTimeValidationError("Work date is required.")
        if not work_type or len(work_type.strip())>60: raise EmployeeWorkingTimeValidationError("Work type is required and must be at most 60 characters.")
        with self._sf() as s:
            repo=EmployeeWorkingTimeRepository(s); self._assert_no_overlap(repo,employee_id,work_date,start_time,end_time)
            e=EmployeeWorkingTimeEntry(employee_id=employee_id,work_date=work_date,start_time=start_time,end_time=end_time,work_type=work_type.strip(),source=EmployeeWorkingTimeEntry.SOURCE_MANUAL,status=EmployeeWorkingTimeEntry.STATUS_BOOKED,notes=notes or None,created_by_user_id=u.id)
            s.add(e); s.commit(); s.refresh(e); return e

    def check_in(self, employee_id, at: datetime | None = None, work_type="WORK", notes=None, user=None):
        u=self._user(user); self._assert_write_scope(employee_id,u); at=at or datetime.now()
        with self._sf() as s:
            repo=EmployeeWorkingTimeRepository(s)
            if repo.open_entry(employee_id): raise EmployeeWorkingTimeValidationError("You already have an open working-time entry. Check out first.")
            e=EmployeeWorkingTimeEntry(employee_id=employee_id,work_date=at.date(),start_time=at.time().replace(second=0,microsecond=0),end_time=None,work_type=(work_type or "WORK").strip(),source=EmployeeWorkingTimeEntry.SOURCE_CHECK_IN,status=EmployeeWorkingTimeEntry.STATUS_OPEN,notes=notes or None,created_by_user_id=u.id)
            s.add(e); s.commit(); s.refresh(e); return e

    def check_out(self, entry_id, at: datetime | None = None, user=None):
        u=self._user(user); at=at or datetime.now()
        with self._sf() as s:
            repo=EmployeeWorkingTimeRepository(s); e=repo.get(entry_id)
            if not e: raise EmployeeWorkingTimeValidationError(f"Working-time entry {entry_id} not found.")
            self._assert_write_scope(e.employee_id,u)
            if e.status != EmployeeWorkingTimeEntry.STATUS_OPEN: raise EmployeeWorkingTimeValidationError("Only an open entry can be checked out.")
            if e.work_date != at.date(): raise EmployeeWorkingTimeValidationError("Check-out must be on the same work date as check-in.")
            end=at.time().replace(second=0,microsecond=0); self._validate_times(e.start_time,end); e.end_time=end; e.status=EmployeeWorkingTimeEntry.STATUS_BOOKED
            s.commit(); s.refresh(e); return e

    def update_booking(self, entry_id, *, work_date, start_time, end_time, work_type, notes=None, user=None):
        u=self._user(user)
        with self._sf() as s:
            repo=EmployeeWorkingTimeRepository(s); e=repo.get(entry_id)
            if not e: raise EmployeeWorkingTimeValidationError(f"Working-time entry {entry_id} not found.")
            self._assert_write_scope(e.employee_id,u); self._validate_times(start_time,end_time)
            if e.status in {EmployeeWorkingTimeEntry.STATUS_APPROVED, EmployeeWorkingTimeEntry.STATUS_LOCKED}: raise EmployeeWorkingTimeAccessDeniedError("Approved or locked working time cannot be edited.")
            self._assert_no_overlap(repo,e.employee_id,work_date,start_time,end_time,e.id)
            e.work_date=work_date;e.start_time=start_time;e.end_time=end_time;e.work_type=work_type.strip();e.notes=notes or None
            e.status=EmployeeWorkingTimeEntry.STATUS_BOOKED
            s.commit();s.refresh(e);return e

    def delete_entry(self, entry_id, user=None):
        u=self._user(user)
        with self._sf() as s:
            repo=EmployeeWorkingTimeRepository(s); e=repo.get(entry_id)
            if not e:return
            self._assert_write_scope(e.employee_id,u)
            if e.status in {EmployeeWorkingTimeEntry.STATUS_APPROVED, EmployeeWorkingTimeEntry.STATUS_LOCKED}: raise EmployeeWorkingTimeAccessDeniedError("Approved or locked working time cannot be deleted.")
            s.delete(e);s.commit()

    def approve(self, entry_id, user=None):
        u=self._user(user)
        if not self._has(u,self.MANAGE): raise EmployeeWorkingTimeAccessDeniedError(f"Permission '{self.MANAGE}' is required.")
        with self._sf() as s:
            e=EmployeeWorkingTimeRepository(s).get(entry_id)
            if not e: raise EmployeeWorkingTimeValidationError("Working-time entry not found.")
            if e.end_time is None: raise EmployeeWorkingTimeValidationError("Open entry must be checked out before approval.")
            e.status=EmployeeWorkingTimeEntry.STATUS_APPROVED;e.approved_by_user_id=u.id;s.commit();s.refresh(e);return e

    def lock_month(self, employee_id, year, month, user=None):
        u=self._user(user)
        if not self._has(u,self.LOCK): raise EmployeeWorkingTimeAccessDeniedError(f"Permission '{self.LOCK}' is required.")
        start=date(year,month,1); end=date(year+1,1,1)-timedelta(days=1) if month==12 else date(year,month+1,1)-timedelta(days=1)
        with self._sf() as s:
            self._scope(employee_id,u)
            rows=EmployeeWorkingTimeRepository(s).list_for_employee(employee_id,start,end)
            if any(r.end_time is None for r in rows): raise EmployeeWorkingTimeValidationError("Cannot lock a month containing open entries.")
            for r in rows: r.status=EmployeeWorkingTimeEntry.STATUS_LOCKED
            s.commit(); return len(rows)

    def monthly_summary(self, employee_id, year, month, user=None):
        u=self._user(user)
        rows=self.list_entries(employee_id,date(year,month,1),date(year+1,1,1)-timedelta(days=1) if month==12 else date(year,month+1,1)-timedelta(days=1),u)
        actual=sum(self._minutes(r.start_time,r.end_time) for r in rows)
        expected=0
        if self._schedule:
            d=date(year,month,1)
            end=date(year+1,1,1) if month==12 else date(year,month+1,1)
            while d<end:
                expected += sum(self._minutes(a,b) for a,b in self._schedule.expected_for_date(employee_id,d,u))
                d += timedelta(days=1)
        return {"year":year,"month":month,"entries":len(rows),"actual_minutes":actual,"expected_minutes":expected,"overtime_minutes":max(0,actual-expected),"shortfall_minutes":max(0,expected-actual)}
