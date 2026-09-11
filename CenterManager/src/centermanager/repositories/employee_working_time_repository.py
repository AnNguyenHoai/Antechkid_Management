from __future__ import annotations
from datetime import date
from typing import Optional
from sqlalchemy.orm import Session
from centermanager.models.employee_working_time import EmployeeWorkingTimeEntry


class EmployeeWorkingTimeRepository:
    def __init__(self, session: Session): self._s = session

    def get(self, entry_id: int) -> Optional[EmployeeWorkingTimeEntry]:
        return self._s.get(EmployeeWorkingTimeEntry, entry_id)

    def list_for_employee(self, employee_id: int, start_date: date | None = None, end_date: date | None = None):
        q = self._s.query(EmployeeWorkingTimeEntry).filter_by(employee_id=employee_id)
        if start_date: q = q.filter(EmployeeWorkingTimeEntry.work_date >= start_date)
        if end_date: q = q.filter(EmployeeWorkingTimeEntry.work_date <= end_date)
        return q.order_by(EmployeeWorkingTimeEntry.work_date.desc(), EmployeeWorkingTimeEntry.start_time.desc()).all()

    def open_entry(self, employee_id: int):
        return self._s.query(EmployeeWorkingTimeEntry).filter_by(employee_id=employee_id, status=EmployeeWorkingTimeEntry.STATUS_OPEN).order_by(EmployeeWorkingTimeEntry.id.desc()).first()

    def add(self, entry: EmployeeWorkingTimeEntry) -> EmployeeWorkingTimeEntry:
        self._s.add(entry)
        self._s.flush()
        self._s.refresh(entry)
        return entry

    def update_booking(self, entry: EmployeeWorkingTimeEntry, *, work_date, start_time, end_time, work_type, notes=None) -> EmployeeWorkingTimeEntry:
        entry.work_date = work_date
        entry.start_time = start_time
        entry.end_time = end_time
        entry.work_type = work_type
        entry.notes = notes or None
        entry.status = EmployeeWorkingTimeEntry.STATUS_BOOKED
        self._s.flush()
        self._s.refresh(entry)
        return entry

    def check_out(self, entry: EmployeeWorkingTimeEntry, end_time) -> EmployeeWorkingTimeEntry:
        entry.end_time = end_time
        entry.status = EmployeeWorkingTimeEntry.STATUS_BOOKED
        self._s.flush()
        self._s.refresh(entry)
        return entry

    def approve(self, entry: EmployeeWorkingTimeEntry, user_id: int) -> EmployeeWorkingTimeEntry:
        entry.status = EmployeeWorkingTimeEntry.STATUS_APPROVED
        entry.approved_by_user_id = user_id
        self._s.flush()
        self._s.refresh(entry)
        return entry

    def delete(self, entry: EmployeeWorkingTimeEntry) -> None:
        self._s.delete(entry)

    def lock_entries(self, entries) -> int:
        count = 0
        for entry in entries:
            entry.status = EmployeeWorkingTimeEntry.STATUS_LOCKED
            count += 1
        self._s.flush()
        return count
