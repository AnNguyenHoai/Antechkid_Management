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
