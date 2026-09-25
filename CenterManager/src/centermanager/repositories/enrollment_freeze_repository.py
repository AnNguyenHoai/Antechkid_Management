"""Persistence boundary for EnrollmentFreeze history."""
from typing import List, Optional

from sqlalchemy.orm import Session

from centermanager.models.enrollment_freeze import EnrollmentFreeze
from centermanager.repositories.base import BaseRepository


class EnrollmentFreezeRepository(BaseRepository[EnrollmentFreeze]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, EnrollmentFreeze)

    def list_for_enrollment(self, enrollment_id: int) -> List[EnrollmentFreeze]:
        return (
            self._session.query(EnrollmentFreeze)
            .filter(EnrollmentFreeze.enrollment_id == enrollment_id)
            .order_by(EnrollmentFreeze.start_session, EnrollmentFreeze.id)
            .all()
        )

    def get_open(self, enrollment_id: int) -> Optional[EnrollmentFreeze]:
        return (
            self._session.query(EnrollmentFreeze)
            .filter(
                EnrollmentFreeze.enrollment_id == enrollment_id,
                EnrollmentFreeze.end_session.is_(None),
            )
            .order_by(EnrollmentFreeze.id.desc())
            .first()
        )

    def add(self, freeze: EnrollmentFreeze) -> EnrollmentFreeze:
        self._session.add(freeze)
        return freeze

    def flush(self) -> None:
        self._session.flush()

    def refresh(self, freeze: EnrollmentFreeze) -> None:
        self._session.refresh(freeze)
