"""
Enrollment repository - data access for Enrollment entity.
"""
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

from centermanager.models.enrollment import Enrollment
from centermanager.models.student import Student
from centermanager.repositories.base import BaseRepository


class EnrollmentRepository(BaseRepository[Enrollment]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Enrollment)

    def exists(self, student_id: int, class_id: int, active_only: bool = True) -> bool:
        """Check enrollment existence. By default only ACTIVE rows are operational."""
        query = self._session.query(Enrollment).filter(
            Enrollment.student_id == student_id,
            Enrollment.class_id == class_id,
        )
        if active_only:
            query = query.filter(Enrollment.status == "ACTIVE")
        return query.first() is not None

    def get_active(self, student_id: int, class_id: int) -> Optional[Enrollment]:
        return self._session.query(Enrollment).filter(
            Enrollment.student_id == student_id,
            Enrollment.class_id == class_id,
            Enrollment.status == "ACTIVE",
        ).first()

    def get_active_by_class(self, class_id: int) -> List[Enrollment]:
        return self._session.query(Enrollment).filter(
            Enrollment.class_id == class_id,
            Enrollment.status == "ACTIVE",
        ).order_by(Enrollment.id).all()

    def get_by_student_and_class(self, student_id: int, class_id: int) -> List[Enrollment]:
        return self._session.query(Enrollment).filter(
            Enrollment.student_id == student_id,
            Enrollment.class_id == class_id,
        ).order_by(desc(Enrollment.created_at)).all()

    def get_by_student(self, student_id: int) -> List[Enrollment]:
        return self._session.query(Enrollment).filter(
            Enrollment.student_id == student_id
        ).order_by(desc(Enrollment.created_at)).all()

    def get_by_class(self, class_id: int) -> List[Enrollment]:
        return self._session.query(Enrollment).filter(
            Enrollment.class_id == class_id
        ).order_by(Enrollment.id).all()

    def list_for_outstanding(
        self,
        class_id: Optional[int] = None,
        search_text: Optional[str] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Tuple[List[Enrollment], int]:
        """List enrollments used by the Finance outstanding read model."""
        query = self._session.query(Enrollment).join(Enrollment.student).filter(
            Enrollment.class_id.isnot(None)
        )
        if class_id is not None:
            query = query.filter(Enrollment.class_id == class_id)
        if search_text:
            search = f"%{search_text}%"
            query = query.filter(
                or_(
                    Student.full_name.ilike(search),
                    Student.student_code.ilike(search),
                )
            )
        total = query.count()
        return query.offset(offset).limit(limit).all(), total

    def get_by_class_with_student(self, class_id: int) -> List[Enrollment]:
        from sqlalchemy.orm import joinedload
        return self._session.query(Enrollment).options(
            joinedload(Enrollment.student)
        ).filter(Enrollment.class_id == class_id).order_by(Enrollment.id).all()

    def add(self, enrollment: Enrollment) -> Enrollment:
        self._session.add(enrollment)
        return enrollment

    def delete(self, enrollment: Enrollment) -> None:
        self._session.delete(enrollment)
