# -*- coding: utf-8 -*-
"""
TeacherDocument repository - data access for TeacherDocument entity.
"""
from typing import List

from sqlalchemy.orm import Session
from sqlalchemy import desc

from centermanager.models.teacher_document import TeacherDocument
from centermanager.repositories.base import BaseRepository


class TeacherDocumentRepository(BaseRepository[TeacherDocument]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, TeacherDocument)

    def get_by_teacher(self, teacher_id: int) -> List[TeacherDocument]:
        return self._session.query(TeacherDocument).filter(
            TeacherDocument.teacher_id == teacher_id
        ).order_by(desc(TeacherDocument.created_at)).all()

    def add(self, document: TeacherDocument) -> TeacherDocument:
        self._session.add(document)
        return document

    def delete(self, document: TeacherDocument) -> None:
        self._session.delete(document)