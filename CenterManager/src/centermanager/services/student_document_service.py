# -*- coding: utf-8 -*-
"""
StudentDocumentService - business logic for Document entity.
"""
import shutil
from pathlib import Path
from typing import List, Optional

from sqlalchemy.orm import sessionmaker

from centermanager.models.document import Document
from centermanager.models.timeline_event import TimelineEventType
from centermanager.repositories.provider import RepositoryProvider
from centermanager.services.timeline_service import TimelineService
from centermanager.core.paths import get_paths


class StudentDocumentService:
    """Application service for student document lifecycle and file handling."""

    def __init__(
        self,
        session_factory: sessionmaker,
        timeline_service: Optional[TimelineService] = None,
        repository_provider: Optional[RepositoryProvider] = None,
    ):
        self._session_factory = session_factory
        self._timeline_service = timeline_service
        self._repository_provider = repository_provider
        if self._repository_provider is None:
            from centermanager.repositories.provider import SqlAlchemyRepositoryProvider
            self._repository_provider = SqlAlchemyRepositoryProvider()

    def _normalize_text(self, text: Optional[str]) -> Optional[str]:
        if text is None:
            return None
        stripped = text.strip()
        return stripped if stripped else None

    def upload_document(
        self,
        student_id: int,
        student_code: str,
        source_path: Path,
        file_name: str,
        document_type: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Document:
        attachment_root = get_paths().attachment_dir
        student_folder = attachment_root / student_code
        student_folder.mkdir(parents=True, exist_ok=True)

        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = f"{timestamp}_{file_name}"
        dest_path = student_folder / safe_name

        shutil.copy2(source_path, dest_path)
        relative_path = f"{student_code}/{safe_name}"

        with self._session_factory() as session:
            repo = self._repository_provider.documents(session)
            doc = Document(
                student_id=student_id,
                file_name=file_name,
                file_path=relative_path,
                document_type=self._normalize_text(document_type),
                description=self._normalize_text(description),
            )
            repo.add(doc)
            session.commit()
            repo.refresh(doc)

            if self._timeline_service:
                self._timeline_service.log_event(
                    student_id=student_id,
                    event_type=TimelineEventType.DOCUMENT_UPLOADED,
                    title="Document Uploaded",
                    description=f"Uploaded {file_name}",
                    metadata={"document_id": doc.id, "document_type": document_type},
                )
            return doc

    def get_documents_for_student(self, student_id: int) -> List[Document]:
        with self._session_factory() as session:
            repo = self._repository_provider.documents(session)
            return repo.get_by_student(student_id)

    def delete_document(self, document_id: int) -> None:
        with self._session_factory() as session:
            repo = self._repository_provider.documents(session)
            doc = repo.get_by_id(document_id)
            if doc is None:
                raise ValueError(f"Document with id {document_id} not found.")
            file_path = get_paths().attachment_dir / doc.file_path
            if file_path.exists():
                file_path.unlink()
            repo.delete(doc)
            session.commit()
