from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Session, joinedload
from centermanager.models.employee_work_registration import EmployeeWorkRegistration, EmployeeWorkRegistrationBlock


class EmployeeWorkRegistrationRepository:
    def __init__(self, session: Session):
        self._s = session

    def get(self, registration_id: int) -> Optional[EmployeeWorkRegistration]:
        return (
            self._s.query(EmployeeWorkRegistration)
            .options(joinedload(EmployeeWorkRegistration.employee), joinedload(EmployeeWorkRegistration.blocks))
            .filter(EmployeeWorkRegistration.id == registration_id)
            .first()
        )

    def get_by_employee_period(self, employee_id: int, period_id: int) -> Optional[EmployeeWorkRegistration]:
        return (
            self._s.query(EmployeeWorkRegistration)
            .options(joinedload(EmployeeWorkRegistration.employee), joinedload(EmployeeWorkRegistration.blocks))
            .filter(EmployeeWorkRegistration.employee_id == employee_id, EmployeeWorkRegistration.period_id == period_id)
            .first()
        )

    def list_all(self, period_id: int):
        return (
            self._s.query(EmployeeWorkRegistration)
            .options(joinedload(EmployeeWorkRegistration.employee), joinedload(EmployeeWorkRegistration.blocks))
            .filter(EmployeeWorkRegistration.period_id == period_id)
            .order_by(EmployeeWorkRegistration.employee_id)
            .all()
        )

    def list_for_employee(self, employee_id: int, period_id: int):
        return (
            self._s.query(EmployeeWorkRegistration)
            .options(joinedload(EmployeeWorkRegistration.employee), joinedload(EmployeeWorkRegistration.blocks))
            .filter(EmployeeWorkRegistration.employee_id == employee_id, EmployeeWorkRegistration.period_id == period_id)
            .all()
        )

    def get_block(self, block_id: int) -> Optional[EmployeeWorkRegistrationBlock]:
        return (
            self._s.query(EmployeeWorkRegistrationBlock)
            .options(joinedload(EmployeeWorkRegistrationBlock.registration))
            .filter(EmployeeWorkRegistrationBlock.id == block_id)
            .first()
        )
