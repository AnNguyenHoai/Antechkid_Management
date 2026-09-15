from __future__ import annotations

from datetime import date, time
from typing import Optional
from sqlalchemy.orm import Session, joinedload
from centermanager.models.employee_work_registration import EmployeeWorkRegistration, EmployeeWorkRegistrationBlock


class EmployeeWorkRegistrationRepository:
    def __init__(self, session: Session):
        self._s = session

    def begin_write(self) -> None:
        """Acquire SQLite's write-intent lock before an EWR mutation."""
        if self._s.get_bind().dialect.name == "sqlite":
            self._s.connection().exec_driver_sql("BEGIN IMMEDIATE")

    def flush(self) -> None:
        """Flush pending EWR changes inside the caller-owned transaction."""
        self._s.flush()

    def refresh(self, entity) -> None:
        """Refresh an EWR entity from the caller-owned transaction/session."""
        self._s.refresh(entity)

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

    def create(self, employee_id: int, period_id: int, status: str) -> EmployeeWorkRegistration:
        registration = EmployeeWorkRegistration(employee_id=employee_id, period_id=period_id, status=status)
        self._s.add(registration)
        self._s.flush()
        return registration

    def add_block(self, registration_id: int, work_date: date, start_time: time, end_time: time, work_type: str, notes: Optional[str] = None) -> EmployeeWorkRegistrationBlock:
        block = EmployeeWorkRegistrationBlock(registration_id=registration_id, work_date=work_date, start_time=start_time, end_time=end_time, work_type=work_type, notes=notes)
        self._s.add(block)
        self._s.flush()
        return block

    def update_block(self, block_id: int, work_date: date, start_time: time, end_time: time, work_type: str, notes: Optional[str] = None) -> EmployeeWorkRegistrationBlock:
        block = self.get_block(block_id)
        if block is None:
            return None
        block.work_date = work_date
        block.start_time = start_time
        block.end_time = end_time
        block.work_type = work_type
        block.notes = notes
        return block

    def delete_block(self, block_id: int) -> Optional[EmployeeWorkRegistrationBlock]:
        block = self.get_block(block_id)
        if block is not None:
            self._s.delete(block)
        return block

    def delete(self, registration_id: int) -> Optional[EmployeeWorkRegistration]:
        registration = self.get(registration_id)
        if registration is not None:
            self._s.delete(registration)
        return registration
