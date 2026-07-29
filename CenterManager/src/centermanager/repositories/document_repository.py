# -*- coding: utf-8 -*-
"""
Document repository - data access for Document entity.
"""
from typing import List

from sqlalchemy.orm import Session
from sqlalchemy import desc

from centermanager.models.document import Document
from centermanager.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Document)

    def get_by_student(self, student_id: int) -> List[Document]:
        return self._session.query(Document).filter(
            Document.student_id == student_id
        ).order_by(desc(Document.created_at)).all()

    def add(self, document: Document) -> Document:
        self._session.add(document)
        return document

    def delete(self, document: Document) -> None:
        self._session.delete(document)