"""Student repository with domain-specific queries."""
import re
from typing import Optional, List
from sqlalchemy.orm import Session, selectinload
from centermanager.models.student import Student
from centermanager.models.enrollment import Enrollment
from centermanager.models.class_ import Class
from centermanager.repositories.base import BaseRepository
from centermanager.models.parent import Parent


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
        """List students considered active by the Home Workspace."""
        return self._session.query(Student).filter(
            Student.deleted_at.is_(None),
            Student.status != "ARCHIVED",
        ).order_by(Student.student_code).all()

    def list_all_including_deleted(self) -> List[Student]:
        return self._session.query(Student).all()

    def get_all_student_codes(self) -> List[str]:
        results = self._session.query(Student.student_code).all()
        return [r[0] for r in results]

    def get_highest_hs_number(self) -> Optional[int]:
        pattern = re.compile(r"^HS(\d+)$")
        max_num = None
        for code in self.get_all_student_codes():
            if code is None:
                continue
            match = pattern.match(code)
            if match:
                num = int(match.group(1))
                if max_num is None or num > max_num:
                    max_num = num
        return max_num

    def search_students(self, query: str) -> List[Student]:
        from sqlalchemy import or_
        q = self._session.query(Student).filter(Student.deleted_at.is_(None))
        if query:
            q = q.outerjoin(Student.parents).filter(
                or_(Student.student_code.ilike(f"%{query}%"), Student.full_name.ilike(f"%{query}%"), Parent.phone.ilike(f"%{query}%"), Parent.name.ilike(f"%{query}%"))
            ).distinct()
        return q.all()

    def get_with_relations(self, student_id: int) -> Optional[Student]:
        return (self._session.query(Student).options(
            selectinload(Student.enrollments).selectinload(Enrollment.class_).selectinload(Class.teachers),
            selectinload(Student.parents), selectinload(Student.notes_structured), selectinload(Student.assessments),
        ).filter(Student.id == student_id, Student.deleted_at.is_(None)).first())
