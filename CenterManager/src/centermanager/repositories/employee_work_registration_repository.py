from __future__ import annotations
from datetime import date
from typing import Optional
from sqlalchemy.orm import Session
from centermanager.models.employee_work_registration import EmployeeWorkRegistration

class EmployeeWorkRegistrationRepository:
    def __init__(self, session: Session): self._s = session
    def get(self, registration_id: int) -> Optional[EmployeeWorkRegistration]: return self._s.get(EmployeeWorkRegistration, registration_id)
    def list_all(self, start_date: date, end_date: date):
        return (self._s.query(EmployeeWorkRegistration)
                .join(EmployeeWorkRegistration.employee)
                .filter(EmployeeWorkRegistration.work_date >= start_date, EmployeeWorkRegistration.work_date <= end_date)
                .order_by(EmployeeWorkRegistration.employee_id, EmployeeWorkRegistration.work_date, EmployeeWorkRegistration.start_time).all())

    def list_for_employee(self, employee_id: int, start_date: date, end_date: date):
        return (self._s.query(EmployeeWorkRegistration)
                .filter(EmployeeWorkRegistration.employee_id == employee_id,
                        EmployeeWorkRegistration.work_date >= start_date,
                        EmployeeWorkRegistration.work_date <= end_date)
                .order_by(EmployeeWorkRegistration.work_date, EmployeeWorkRegistration.start_time).all())
