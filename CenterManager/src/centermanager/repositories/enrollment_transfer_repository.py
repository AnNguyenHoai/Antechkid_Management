"""Persistence adapter for EnrollmentTransfer ledger rows."""
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from centermanager.models.class_ import Class
from centermanager.models.enrollment import Enrollment
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

    def flush_guarded(self) -> bool:
        """Flush and report a uniqueness race; transaction lifecycle stays service-owned."""
        try:
            self._session.flush()
            return True
        except IntegrityError:
            return False

    def refresh(self, transfer: EnrollmentTransfer) -> None:
        self._session.refresh(transfer)

    def acquire_command_lock(
        self, source_enrollment_id: int, target_class_id: int
    ) -> Tuple[Optional[Enrollment], Optional[Class]]:
        """Serialize transfer check-then-act operations at the repository boundary.

        SQLite has no row-level ``FOR UPDATE`` support, so ``BEGIN IMMEDIATE``
        obtains the single writer reservation before any balance/capacity read.
        Other supported relational databases lock the source Enrollment and
        target Class rows, which serializes double-transfer and last-slot races.
        """
        bind = self._session.get_bind()
        dialect = getattr(getattr(bind, "dialect", None), "name", "")
        if dialect == "sqlite":
            self._session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            source_query = self._session.query(Enrollment)
            class_query = self._session.query(Class)
        else:
            source_query = self._session.query(Enrollment).with_for_update()
            class_query = self._session.query(Class).with_for_update()

        source = source_query.options(joinedload(Enrollment.freezes)).filter(
            Enrollment.id == source_enrollment_id
        ).first()
        target_class = class_query.filter(Class.id == target_class_id).first()
        return source, target_class

    def get_for_target(self, target_enrollment_id: int) -> Optional[EnrollmentTransfer]:
        return self._session.query(EnrollmentTransfer).filter(
            EnrollmentTransfer.target_enrollment_id == target_enrollment_id
        ).first()

    def get_for_source(self, source_enrollment_id: int) -> Optional[EnrollmentTransfer]:
        return self._session.query(EnrollmentTransfer).options(
            joinedload(EnrollmentTransfer.target_enrollment)
        ).filter(
            EnrollmentTransfer.source_enrollment_id == source_enrollment_id
        ).first()

    def get_by_idempotency_key(self, key: str) -> Optional[EnrollmentTransfer]:
        return self._session.query(EnrollmentTransfer).options(
            joinedload(EnrollmentTransfer.target_enrollment)
        ).filter(EnrollmentTransfer.idempotency_key == key).first()

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
