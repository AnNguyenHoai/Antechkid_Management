# -*- coding: utf-8 -*-
"""
Class repository - data access for Class entity.
"""
from typing import List, Optional
import re

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from centermanager.models.class_ import Class
from centermanager.models.enrollment import Enrollment
from centermanager.repositories.base import BaseRepository


class ClassRepository(BaseRepository[Class]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Class)

    def get_by_name(self, name: str) -> Optional[Class]:
        return self._session.query(Class).filter(Class.name == name).first()

    def list_active(self) -> List[Class]:
        return self._session.query(Class).options(
            joinedload(Class.teachers),
            joinedload(Class.enrollments)
        ).filter(
            Class.deleted_at.is_(None)
        ).order_by(Class.name).all()

    def list_archived(self) -> List[Class]:
        return self._session.query(Class).options(
            joinedload(Class.teachers),
            joinedload(Class.enrollments)
        ).filter(
            Class.deleted_at.is_not(None)
        ).order_by(Class.name).all()

    def list_all(self) -> List[Class]:
        return self._session.query(Class).options(
            joinedload(Class.teachers),
            joinedload(Class.enrollments)
        ).order_by(Class.name).all()

    def get_by_id_with_relations(self, class_id: int) -> Optional[Class]:
        return self._session.query(Class).options(
            joinedload(Class.teachers),
            joinedload(Class.enrollments).joinedload(Enrollment.student)
        ).filter(Class.id == class_id).first()

    def search_classes(self, query: str) -> List[Class]:
        q = self._session.query(Class).options(
            joinedload(Class.teachers),
            joinedload(Class.enrollments)
        ).filter(Class.deleted_at.is_(None))
        if query:
            q = q.filter(
                or_(
                    Class.name.ilike(f"%{query}%"),
                    Class.course.ilike(f"%{query}%"),
                    Class.teacher.ilike(f"%{query}%")
                )
            )
        return q.all()

    def get_highest_class_number(self) -> Optional[int]:
        all_codes = [c.name for c in self._session.query(Class.name).all() if c.name]
        pattern = re.compile(r"^CLS(\d+)$")
        max_num = None
        for code in all_codes:
            match = pattern.match(code)
            if match:
                num = int(match.group(1))
                if max_num is None or num > max_num:
                    max_num = num
        return max_num

    def add(self, class_obj: Class) -> Class:
        self._session.add(class_obj)
        return class_obj

    def delete(self, class_obj: Class) -> None:
        self._session.delete(class_obj)