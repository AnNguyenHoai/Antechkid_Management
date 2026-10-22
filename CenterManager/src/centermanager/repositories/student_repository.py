"""Student repository with domain-specific queries."""
import re
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import and_, asc, desc, or_
from centermanager.models.student import Student
from centermanager.models.enrollment import Enrollment
from centermanager.models.assessment import Assessment
from centermanager.models.class_ import Class
from centermanager.repositories.base import BaseRepository
from centermanager.models.parent import Parent
from centermanager.dto.student_filter_dto import StudentFilter

class StudentRepository(BaseRepository[Student]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Student)

    def get_by_code(self, student_code: str) -> Optional[Student]:
        return self._session.query(Student).filter(Student.student_code == student_code, Student.deleted_at.is_(None)).first()
    def get_by_code_including_deleted(self, student_code: str) -> Optional[Student]:
        return self._session.query(Student).filter(Student.student_code == student_code).first()
    def get_by_id_including_deleted(self, student_id: int) -> Optional[Student]:
        return self._session.get(Student, student_id)
    def list_active(self) -> List[Student]:
        return self._session.query(Student).filter(Student.deleted_at.is_(None)).order_by(Student.student_code).all()
    def list_active_non_archived(self) -> List[Student]:
        return self._session.query(Student).filter(Student.deleted_at.is_(None), Student.status != "ARCHIVED").order_by(Student.student_code).all()
    def list_all_including_deleted(self) -> List[Student]:
        return self._session.query(Student).all()
    def get_all_student_codes(self) -> List[str]:
        results = self._session.query(Student.student_code).all()
        return [r[0] for r in results]
    def get_highest_hs_number(self) -> Optional[int]:
        pattern = re.compile(r"^HS(\d+)$")
        max_num = None
        for code in self.get_all_student_codes():
            if code is None: continue
            match = pattern.match(code)
            if match:
                num = int(match.group(1))
                if max_num is None or num > max_num: max_num = num
        return max_num
    def search_students(self, query: str) -> List[Student]:
        q = (
            self._session.query(Student)
            .options(selectinload(Student.parents))
            .filter(Student.deleted_at.is_(None))
        )
        if query:
            like = f"%{query.strip()}%"
            q = q.filter(
                or_(
                    Student.student_code.ilike(like),
                    Student.full_name.ilike(like),
                    Student.preferred_name.ilike(like),
                    Student.parents.any(
                        or_(Parent.phone.ilike(like), Parent.name.ilike(like))
                    ),
                )
            )
        return q.order_by(Student.student_code.asc()).all()

    def search_page(
        self,
        *,
        search_text: str = "",
        status: Optional[str] = None,
        enrollment_status: Optional[str] = None,
        assessment_status: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
        sort_by: str = "student_code",
        ascending: bool = True,
    ) -> Tuple[List[Student], int]:
        """Server-side Student search/filter page without per-row relationship queries."""
        q = self._session.query(Student).filter(Student.deleted_at.is_(None))

        if status == "ACTIVE":
            q = q.filter(Student.status == "ACTIVE")
        elif status == "ARCHIVED":
            q = q.filter(Student.status == "ARCHIVED")

        if enrollment_status == "enrolled":
            q = q.filter(
                Student.enrollments.any(
                    and_(
                        Enrollment.status == "ACTIVE",
                        Enrollment.reconciled_into_enrollment_id.is_(None),
                    )
                )
            )
        elif enrollment_status == "not_enrolled":
            q = q.filter(
                ~Student.enrollments.any(
                    and_(
                        Enrollment.status == "ACTIVE",
                        Enrollment.reconciled_into_enrollment_id.is_(None),
                    )
                )
            )

        if assessment_status == "has_assessment":
            q = q.filter(Student.assessments.any())
        elif assessment_status == "no_assessment":
            q = q.filter(~Student.assessments.any())

        term = (search_text or "").strip()
        if term:
            like = f"%{term}%"
            q = q.filter(
                or_(
                    Student.student_code.ilike(like),
                    Student.full_name.ilike(like),
                    Student.preferred_name.ilike(like),
                    Student.parents.any(
                        or_(Parent.phone.ilike(like), Parent.name.ilike(like))
                    ),
                )
            )

        total = q.count()
        sort_columns = {
            "student_code": Student.student_code,
            "full_name": Student.full_name,
            "status": Student.status,
            "current_level": Student.current_level,
            "created_at": Student.created_at,
        }
        column = sort_columns.get(sort_by, Student.student_code)
        order = asc(column) if ascending else desc(column)
        rows = (
            q.order_by(order, Student.id.asc())
            .offset(max(0, int(offset)))
            .limit(max(1, int(limit)))
            .all()
        )
        return rows, total
    def get_with_relations(self, student_id: int) -> Optional[Student]:
        return (self._session.query(Student).options(selectinload(Student.enrollments).selectinload(Enrollment.class_).selectinload(Class.teachers), selectinload(Student.parents), selectinload(Student.notes_structured), selectinload(Student.assessments)).filter(Student.id == student_id, Student.deleted_at.is_(None)).first())

    def filter_students(self, filter_criteria: StudentFilter) -> List[Student]:
        """Apply database-backed Student filters; age filtering stays in the service."""
        q = (
            self._session.query(Student)
            .options(selectinload(Student.parents))
            .filter(Student.deleted_at.is_(None))
        )
        if filter_criteria.status == "ARCHIVED":
            q = q.filter(Student.status == "ARCHIVED")
        elif filter_criteria.status == "ACTIVE":
            q = q.filter(Student.status == "ACTIVE")
        if filter_criteria.enrollment_status == "enrolled":
            q = q.join(Student.enrollments).filter(Enrollment.status == "active")
        elif filter_criteria.enrollment_status == "not_enrolled":
            q = q.outerjoin(Student.enrollments).filter(Enrollment.id.is_(None))
        if filter_criteria.assessment_status == "has_assessment":
            q = q.join(Student.assessments).distinct()
        elif filter_criteria.assessment_status == "no_assessment":
            q = q.outerjoin(Student.assessments).filter(Assessment.id.is_(None))
        if filter_criteria.class_name:
            q = q.join(Student.enrollments).join(Enrollment.class_).filter(Class.name == filter_criteria.class_name)
        return q.all()
