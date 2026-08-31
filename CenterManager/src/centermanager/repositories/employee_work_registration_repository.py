from __future__ import annotations
from datetime import date
from typing import Optional
from sqlalchemy.orm import Session, joinedload
from centermanager.models.employee_work_registration import EmployeeWorkRegistration

class EmployeeWorkRegistrationRepository:
    def __init__(self, session: Session): self._s = session

    def get(self, registration_id: int) -> Optional[EmployeeWorkRegistration]:
        # Mutating/service callers only need scalar fields here.  Keep this
        # lightweight rather than eagerly loading the employee graph.
        return self._s.get(EmployeeWorkRegistration, registration_id)

    def list_all(self, start_date: date, end_date: date):
        # The management UI renders the employee name/code after the service
        # session has been closed.  A plain JOIN filters rows but does NOT
        # populate the relationship; accessing r.employee later therefore
        # triggers a lazy load on a detached instance.
        #
        # joinedload makes the relationship part of the query result and
        # removes that session-lifetime dependency.
        return (
            self._s.query(EmployeeWorkRegistration)
            .options(joinedload(EmployeeWorkRegistration.employee))
            .filter(
                EmployeeWorkRegistration.work_date >= start_date,
                EmployeeWorkRegistration.work_date <= end_date,
            )
            .order_by(
                EmployeeWorkRegistration.employee_id,
                EmployeeWorkRegistration.work_date,
                EmployeeWorkRegistration.start_time,
            )
            .all()
        )

    def list_for_employee(self, employee_id: int, start_date: date, end_date: date):
        # Keep self-service results safe for the same detached-object boundary.
        return (
            self._s.query(EmployeeWorkRegistration)
            .options(joinedload(EmployeeWorkRegistration.employee))
            .filter(
                EmployeeWorkRegistration.employee_id == employee_id,
                EmployeeWorkRegistration.work_date >= start_date,
                EmployeeWorkRegistration.work_date <= end_date,
            )
            .order_by(
                EmployeeWorkRegistration.work_date,
                EmployeeWorkRegistration.start_time,
            )
            .all()
        )
