"""
Enrollment repository - data access for Enrollment entity.
"""
from datetime import date
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import case, desc, or_

from centermanager.models.enrollment import Enrollment
from centermanager.models.student import Student
from centermanager.models.class_ import Class
from centermanager.models.parent import Parent
from centermanager.repositories.base import BaseRepository


class EnrollmentRepository(BaseRepository[Enrollment]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Enrollment)

    def exists(self, student_id: int, class_id: int, active_only: bool = True) -> bool:
        query = self._session.query(Enrollment).filter(
            Enrollment.student_id == student_id,
            Enrollment.class_id == class_id,
            Enrollment.reconciled_into_enrollment_id.is_(None),
        )
        if active_only:
            query = query.filter(Enrollment.status == "ACTIVE")
        return query.first() is not None

    def exists_on_date(self, student_id: int, class_id: int, on_date: date) -> bool:
        return (
            self._session.query(Enrollment.id)
            .filter(
                Enrollment.student_id == student_id,
                Enrollment.class_id == class_id,
                Enrollment.reconciled_into_enrollment_id.is_(None),
                or_(Enrollment.start_date.is_(None), Enrollment.start_date <= on_date),
                or_(Enrollment.end_date.is_(None), Enrollment.end_date >= on_date),
            )
            .first()
            is not None
        )

    def get_active(self, student_id: int, class_id: int) -> Optional[Enrollment]:
        return self._session.query(Enrollment).options(
            joinedload(Enrollment.freezes)
        ).filter(
            Enrollment.student_id == student_id,
            Enrollment.class_id == class_id,
            Enrollment.status == "ACTIVE",
            Enrollment.reconciled_into_enrollment_id.is_(None),
        ).first()

    def get_active_by_class(self, class_id: int) -> List[Enrollment]:
        return self._session.query(Enrollment).options(
            joinedload(Enrollment.freezes)
        ).filter(
            Enrollment.class_id == class_id,
            Enrollment.status == "ACTIVE",
            Enrollment.reconciled_into_enrollment_id.is_(None),
        ).order_by(Enrollment.id).all()

    def get_by_student_and_class(self, student_id: int, class_id: int) -> List[Enrollment]:
        return self._session.query(Enrollment).options(
            joinedload(Enrollment.freezes)
        ).filter(
            Enrollment.student_id == student_id,
            Enrollment.class_id == class_id,
            Enrollment.reconciled_into_enrollment_id.is_(None),
        ).order_by(desc(Enrollment.created_at)).all()

    def get_by_student_and_class_including_reconciled(
        self, student_id: int, class_id: int
    ) -> List[Enrollment]:
        return self._session.query(Enrollment).options(
            joinedload(Enrollment.freezes)
        ).filter(
            Enrollment.student_id == student_id,
            Enrollment.class_id == class_id,
        ).order_by(desc(Enrollment.created_at), desc(Enrollment.id)).all()

    def get_by_student(self, student_id: int) -> List[Enrollment]:
        return self._session.query(Enrollment).options(
            joinedload(Enrollment.freezes)
        ).filter(
            Enrollment.student_id == student_id
        ).order_by(desc(Enrollment.created_at)).all()

    def search_tuition_payment_candidates(
        self,
        query: str = "",
        *,
        mode: str = "ACTIVE",
        limit: int = 20,
    ) -> List[Enrollment]:
        """Search Enrollment identities for tuition payment entry.

        Modes:
        - ACTIVE: current operational contracts only; archived Students/Classes hidden.
        - OLD_DEBT: historical contracts; archived Students/Classes remain eligible
          because archival must not erase outstanding financial obligations.
        - ALL: all canonical contracts for non-deleted Students.

        Debt itself is calculated by IncomeService from the canonical tuition
        accrual/settlement policy; this repository only scopes candidate identities.
        """
        normalized_mode = (mode or "ACTIVE").upper()
        if normalized_mode not in {"ACTIVE", "OLD_DEBT", "ALL"}:
            raise ValueError(f"Unsupported tuition picker mode: {mode}")

        q = (
            self._session.query(Enrollment)
            .options(
                joinedload(Enrollment.student),
                joinedload(Enrollment.class_),
                joinedload(Enrollment.freezes),
            )
            .join(Enrollment.student)
            .join(Enrollment.class_)
            .outerjoin(Student.parents)
            .filter(
                Enrollment.reconciled_into_enrollment_id.is_(None),
                Student.deleted_at.is_(None),
            )
        )

        if normalized_mode == "ACTIVE":
            q = q.filter(
                Enrollment.status == "ACTIVE",
                Student.status != "ARCHIVED",
                Class.deleted_at.is_(None),
            )
        elif normalized_mode == "OLD_DEBT":
            q = q.filter(Enrollment.status.in_(("WITHDRAWN", "COMPLETED")))

        term = (query or "").strip()
        if term:
            like = f"%{term}%"
            q = q.filter(
                or_(
                    Student.student_code.ilike(like),
                    Student.full_name.ilike(like),
                    Student.preferred_name.ilike(like),
                    Parent.name.ilike(like),
                    Parent.phone.ilike(like),
                    Class.name.ilike(like),
                    Class.course.ilike(like),
                    Enrollment.class_name.ilike(like),
                    Enrollment.course_name.ilike(like),
                )
            )

        active_first = case((Enrollment.status == "ACTIVE", 0), else_=1)
        archived_student_last = case((Student.status == "ARCHIVED", 1), else_=0)
        archived_class_last = case((Class.deleted_at.is_not(None), 1), else_=0)
        return (
            q.distinct()
            .order_by(
                active_first,
                archived_student_last,
                archived_class_last,
                Student.full_name.asc(),
                Class.name.asc(),
                Enrollment.id.desc(),
            )
            .limit(max(1, min(int(limit or 20), 100)))
            .all()
        )

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
        query = (
            self._session.query(Enrollment)
            .options(
                joinedload(Enrollment.student),
                joinedload(Enrollment.class_),
                joinedload(Enrollment.freezes),
            )
            .join(Enrollment.student)
            .filter(
                Enrollment.class_id.isnot(None),
                Enrollment.reconciled_into_enrollment_id.is_(None),
            )
        )
        if class_id is not None:
            query = query.filter(Enrollment.class_id == class_id)
        if course_name:
            search_course = f"%{course_name.strip()}%"
            query = query.join(Enrollment.class_).filter(
                or_(Enrollment.course_name.ilike(search_course), Class.course.ilike(search_course))
            )
        if student_id is not None:
            query = query.filter(Enrollment.student_id == student_id)
        if period_start is not None:
            query = query.filter(or_(Enrollment.end_date.is_(None), Enrollment.end_date >= period_start))
        if period_end is not None:
            query = query.filter(or_(Enrollment.start_date.is_(None), Enrollment.start_date <= period_end))
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
        query = query.order_by(desc(Enrollment.created_at), desc(Enrollment.id)).offset(max(0, offset))
        if limit is not None:
            query = query.limit(max(1, limit))
        return query.all(), total

    def get_by_class(self, class_id: int) -> List[Enrollment]:
        return self._session.query(Enrollment).options(
            joinedload(Enrollment.freezes)
        ).filter(
            Enrollment.class_id == class_id,
            Enrollment.reconciled_into_enrollment_id.is_(None),
        ).order_by(Enrollment.id).all()

    def get_by_class_with_student(self, class_id: int) -> List[Enrollment]:
        return self._session.query(Enrollment).options(
            joinedload(Enrollment.student),
            joinedload(Enrollment.freezes),
        ).filter(
            Enrollment.class_id == class_id,
            Enrollment.reconciled_into_enrollment_id.is_(None),
        ).order_by(Enrollment.id).all()

    def get_by_class_with_student_including_reconciled(self, class_id: int) -> List[Enrollment]:
        return self._session.query(Enrollment).options(
            joinedload(Enrollment.student),
            joinedload(Enrollment.freezes),
        ).filter(
            Enrollment.class_id == class_id,
        ).order_by(Enrollment.id).all()

    def add(self, enrollment: Enrollment) -> Enrollment:
        self._session.add(enrollment)
        return enrollment

    def flush(self) -> None:
        self._session.flush()

    def delete(self, enrollment: Enrollment) -> None:
        self._session.delete(enrollment)
