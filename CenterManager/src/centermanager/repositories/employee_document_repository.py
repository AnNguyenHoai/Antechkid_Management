from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from centermanager.models.employee_document import EmployeeDocument
from centermanager.repositories.base import BaseRepository


class EmployeeDocumentRepository(BaseRepository[EmployeeDocument]):
    """Persistence adapter for employee documents."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, EmployeeDocument)

    def get_by_id(self, document_id: int) -> Optional[EmployeeDocument]:
        return self._session.get(EmployeeDocument, document_id)

    def list_for_employee(self, employee_id: int) -> List[EmployeeDocument]:
        return (
            self._session.query(EmployeeDocument)
            .filter(EmployeeDocument.employee_id == employee_id)
            .order_by(EmployeeDocument.uploaded_at.desc())
            .all()
        )

    def add(self, document: EmployeeDocument) -> EmployeeDocument:
        self._session.add(document)
        return document
