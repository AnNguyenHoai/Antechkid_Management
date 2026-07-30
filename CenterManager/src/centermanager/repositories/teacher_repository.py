# -*- coding: utf-8 -*-
"""
Teacher repository - data access for Teacher entity.
"""
from typing import Optional, List
from datetime import datetime

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, or_

from centermanager.models.teacher import Teacher
from centermanager.repositories.base import BaseRepository


class TeacherRepository(BaseRepository[Teacher]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Teacher)

    def get_by_code(self, teacher_code: str) -> Optional[Teacher]:
        return self._session.query(Teacher).filter(
            Teacher.teacher_code == teacher_code,
            Teacher.deleted_at.is_(None)
        ).first()

    def get_by_code_including_deleted(self, teacher_code: str) -> Optional[Teacher]:
        return self._session.query(Teacher).filter(
            Teacher.teacher_code == teacher_code
        ).first()

    def get_by_id_with_relations(self, teacher_id: int) -> Optional[Teacher]:
        return self._session.query(Teacher).options(
            joinedload(Teacher.documents),
            joinedload(Teacher.assigned_classes)
        ).filter(Teacher.id == teacher_id).first()

    def list_active(self) -> List[Teacher]:
        return self._session.query(Teacher).filter(
            Teacher.deleted_at.is_(None)
        ).order_by(Teacher.teacher_code).all()

    def list_all_including_deleted(self) -> List[Teacher]:
        return self._session.query(Teacher).all()

    def get_all_teacher_codes(self) -> List[str]:
        results = self._session.query(Teacher.teacher_code).all()
        return [r[0] for r in results]

    def get_highest_teacher_number(self) -> Optional[int]:
        import re
        pattern = re.compile(r"^TCH(\d+)$")
        all_codes = self.get_all_teacher_codes()
        max_num = None
        for code in all_codes:
            if code is None:
                continue
            match = pattern.match(code)
            if match:
                num = int(match.group(1))
                if max_num is None or num > max_num:
                    max_num = num
        return max_num

    def search_teachers(self, query: str) -> List[Teacher]:
        q = self._session.query(Teacher).filter(Teacher.deleted_at.is_(None))
        if query:
            q = q.filter(
                or_(
                    Teacher.teacher_code.ilike(f"%{query}%"),
                    Teacher.full_name.ilike(f"%{query}%"),
                    Teacher.phone.ilike(f"%{query}%"),
                    Teacher.email.ilike(f"%{query}%")
                )
            )
        return q.all()

    def add(self, teacher: Teacher) -> Teacher:
        self._session.add(teacher)
        return teacher

    def delete(self, teacher: Teacher) -> None:
        self._session.delete(teacher)