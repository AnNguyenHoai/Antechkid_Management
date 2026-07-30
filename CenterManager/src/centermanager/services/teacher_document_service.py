# -*- coding: utf-8 -*-
"""
TeacherDocumentService - manage teacher documents.
"""
import shutil
from pathlib import Path
from typing import Optional, List

from sqlalchemy.orm import sessionmaker

from centermanager.models.teacher_document import TeacherDocument
from centermanager.models.teacher_timeline_event import TeacherTimelineEventType
from centermanager.repositories.teacher_document_repository import TeacherDocumentRepository
from centermanager.services.teacher_timeline_service import TeacherTimelineService
from centermanager.core.paths import get_paths


class TeacherDocumentService:
    def __init__(
        self,
        session_factory: sessionmaker,
        timeline_service: TeacherTimelineService
    ) -> None:
        self._session_factory = session_factory
        self._timeline_service = timeline_service

    def _normalize_text(self, text: Optional[str]) -> Optional[str]:
        if text is None:
            return None
        stripped = text.strip()
        return stripped if stripped else None

    def upload_document(
        self,
        teacher_id: int,
        teacher_code: str,
        source_path: Path,
        file_name: str,
        document_type: Optional[str] = None,
        description: Optional[str] = None,
    ) -> TeacherDocument:
        attachment_root = get_paths().attachment_dir / "teachers"
        teacher_folder = attachment_root / teacher_code
        teacher_folder.mkdir(parents=True, exist_ok=True)

        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = f"{timestamp}_{file_name}"
        dest_path = teacher_folder / safe_name

        shutil.copy2(source_path, dest_path)
        relative_path = f"teachers/{teacher_code}/{safe_name}"

        with self._session_factory() as session:
            doc = TeacherDocument(
                teacher_id=teacher_id,
                file_name=file_name,
                file_path=relative_path,
                document_type=self._normalize_text(document_type),
                description=self._normalize_text(description),
            )
            repo = TeacherDocumentRepository(session)
            repo.add(doc)
            session.commit()
            session.refresh(doc)

            self._timeline_service.log_event(
                teacher_id=teacher_id,
                event_type=TeacherTimelineEventType.DOCUMENT_UPLOADED,
                title="Document Uploaded",
                description=f"Uploaded {file_name}",
                metadata={"document_id": doc.id, "document_type": document_type}
            )
            return doc

    def get_documents_for_teacher(self, teacher_id: int) -> List[TeacherDocument]:
        with self._session_factory() as session:
            repo = TeacherDocumentRepository(session)
            return repo.get_by_teacher(teacher_id)

    def delete_document(self, document_id: int) -> None:
        with self._session_factory() as session:
            repo = TeacherDocumentRepository(session)
            doc = repo.get_by_id(document_id)
            if doc is None:
                raise ValueError(f"Document {document_id} not found.")
            file_path = get_paths().attachment_dir / doc.file_path
            if file_path.exists():
                file_path.unlink()
            teacher_id = doc.teacher_id
            file_name = doc.file_name
            repo.delete(doc)
            session.commit()

            self._timeline_service.log_event(
                teacher_id=teacher_id,
                event_type=TeacherTimelineEventType.DOCUMENT_DELETED,
                title="Document Deleted",
                description=f"Deleted {file_name}",
            )