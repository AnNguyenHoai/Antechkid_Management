"""Persistence adapter for EnrollmentTransfer ledger rows."""
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from centermanager.models.enrollment_transfer import EnrollmentTransfer
from centermanager.repositories.base import BaseRepository


class EnrollmentTransferRepository(BaseRepository[EnrollmentTransfer]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, EnrollmentTransfer)

    def add(self, transfer: EnrollmentTransfer) -> EnrollmentTransfer:
        self._session.add(transfer)
        return transfer

    def flush(self) -> None:
        self._session.flush()

    def refresh(self, transfer: EnrollmentTransfer) -> None:
        self._session.refresh(transfer)

    def get_for_target(self, target_enrollment_id: int) -> Optional[EnrollmentTransfer]:
        return self._session.query(EnrollmentTransfer).filter(
            EnrollmentTransfer.target_enrollment_id == target_enrollment_id
        ).first()

    def list_for_source(self, source_enrollment_id: int) -> List[EnrollmentTransfer]:
        return self._session.query(EnrollmentTransfer).filter(
            EnrollmentTransfer.source_enrollment_id == source_enrollment_id
        ).order_by(EnrollmentTransfer.id).all()

    def incoming_credit(self, enrollment_id: int) -> Decimal:
        value = self._session.query(func.coalesce(func.sum(EnrollmentTransfer.transferred_credit), 0)).filter(
            EnrollmentTransfer.target_enrollment_id == enrollment_id
        ).scalar()
        return Decimal(str(value or 0))

    def outgoing_credit(self, enrollment_id: int) -> Decimal:
        value = self._session.query(func.coalesce(func.sum(EnrollmentTransfer.transferred_credit), 0)).filter(
            EnrollmentTransfer.source_enrollment_id == enrollment_id
        ).scalar()
        return Decimal(str(value or 0))
