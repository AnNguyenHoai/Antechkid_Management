"""
Enrollment repository - data access for Enrollment entity.
"""
from datetime import date
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, or_

from centermanager.models.enrollment import Enrollment
from centermanager.models.student import Student
from centermanager.models.class_ import Class
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

    def exists_on_date(
        self,
        student_id: int,
        class_id: int,
        on_date: date,
    ) -> bool:
        """Return whether an enrollment covered ``on_date``.

        Historical finance validation is date based, not current-status based:
        COMPLETED/CANCELLED rows remain valid for dates inside their recorded
        start/end interval.
        """
        return (
            self._session.query(Enrollment.id)
            .filter(
                Enrollment.student_id == student_id,
                Enrollment.class_id == class_id,
                or_(Enrollment.start_date.is_(None), Enrollment.start_date <= on_date),
                or_(Enrollment.end_date.is_(None), Enrollment.end_date >= on_date),
            )
            .first()
            is not None
        )

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

    def list_for_outstanding(
        self,
        class_id: Optional[int] = None,
        search_text: Optional[str] = None,
        offset: int = 0,
        limit: Optional[int] = 100,
        course_name: Optional[str] = None,
        student_id: Optional[int] = None,
        period_start=None,
        period_end=None,
    ) -> Tuple[List[Enrollment], int]:
        """List enrollments used by the Finance outstanding read model.

        Student and class relationships are eagerly loaded because Outstanding is a
        read model that needs both for every row. ``limit=None`` is reserved for
        service-side derived filtering/pagination, where status is only known after
        tuition and payment values have been calculated.
        """
        query = (
            self._session.query(Enrollment)
            .options(
                joinedload(Enrollment.student),
                joinedload(Enrollment.class_),
            )
            .join(Enrollment.student)
            .filter(Enrollment.class_id.isnot(None))
        )
        if class_id is not None:
            query = query.filter(Enrollment.class_id == class_id)
        if course_name:
            search_course = f"%{course_name.strip()}%"
            query = query.join(Enrollment.class_).filter(
                or_(
                    Enrollment.course_name.ilike(search_course),
                    Class.course.ilike(search_course),
                )
            )
        if student_id is not None:
            query = query.filter(Enrollment.student_id == student_id)
        if period_start is not None:
            query = query.filter(
                or_(Enrollment.end_date.is_(None), Enrollment.end_date >= period_start)
            )
        if period_end is not None:
            query = query.filter(
                or_(Enrollment.start_date.is_(None), Enrollment.start_date <= period_end)
            )
        if search_text:
            search = f"%{search_text.strip()}%"
            query = query.filter(
                or_(
                    Student.full_name.ilike(search),
                    Student.student_code.ilike(search),
                    Enrollment.course_name.ilike(search),
                    Enrollment.class_name.ilike(search),
                )
            )

        total = query.count()
        query = query.order_by(desc(Enrollment.created_at), desc(Enrollment.id))
        query = query.offset(max(0, offset))
        if limit is not None:
            query = query.limit(max(1, limit))
        return query.all(), total

    def get_by_class(self, class_id: int) -> List[Enrollment]:
        return self._session.query(Enrollment).filter(
            Enrollment.class_id == class_id
        ).order_by(Enrollment.id).all()

    def get_by_class_with_student(self, class_id: int) -> List[Enrollment]:
        return self._session.query(Enrollment).options(
            joinedload(Enrollment.student)
        ).filter(Enrollment.class_id == class_id).order_by(Enrollment.id).all()

    def add(self, enrollment: Enrollment) -> Enrollment:
        self._session.add(enrollment)
        return enrollment

    def flush(self) -> None:
        """Flush pending Enrollment writes without owning the transaction."""
        self._session.flush()

    def delete(self, enrollment: Enrollment) -> None:
        self._session.delete(enrollment)
