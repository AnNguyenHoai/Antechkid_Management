# -*- coding: utf-8 -*-
"""
TeacherDocumentService - manage teacher documents.
"""
import shutil
import uuid
from pathlib import Path
from typing import Optional, List

from sqlalchemy.orm import sessionmaker

from centermanager.models.teacher_document import TeacherDocument
from centermanager.models.teacher_timeline_event import TeacherTimelineEventType
from centermanager.repositories.teacher_document_repository import TeacherDocumentRepository
from centermanager.repositories.teacher_repository import TeacherRepository
from centermanager.services.teacher_timeline_service import TeacherTimelineService
from centermanager.core.paths import get_paths
from centermanager.events.event_bus import EventBus
from centermanager.events.teacher_events import TeacherDocumentChanged


class TeacherDocumentService:
    def __init__(
        self,
        session_factory: sessionmaker,
        timeline_service: TeacherTimelineService,
        event_bus: EventBus | None = None
    ) -> None:
        self._session_factory = session_factory
        self._timeline_service = timeline_service
        self._event_bus = event_bus

    def _normalize_text(self, text: Optional[str]) -> Optional[str]:
        if text is None:
            return None
        stripped = text.strip()
        return stripped if stripped else None


    def get_teacher_code(self, teacher_id: int) -> str:
        with self._session_factory() as session:
            teacher = TeacherRepository(session).get_by_id(teacher_id)
            if teacher is None or teacher.deleted_at is not None:
                raise ValueError(f"Teacher {teacher_id} not found.")
            return teacher.teacher_code

    def upload_document(
        self,
        teacher_id: int,
        teacher_code: str,
        source_path: Path,
        file_name: str,
        document_type: Optional[str] = None,
        description: Optional[str] = None,
    ) -> TeacherDocument:
        source_path = Path(source_path)
        if not source_path.is_file():
            raise ValueError(f"Document source does not exist: {source_path}")

        attachment_root = get_paths().attachment_dir / "teachers"
        teacher_folder = attachment_root / teacher_code
        teacher_folder.mkdir(parents=True, exist_ok=True)

        # A UUID avoids same-second collisions while preserving the original name in DB.
        safe_name = f"{uuid.uuid4().hex}_{source_path.name}"
        dest_path = teacher_folder / safe_name
        relative_path = f"teachers/{teacher_code}/{safe_name}"

        shutil.copy2(source_path, dest_path)

        try:
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
        except Exception:
            # Compensate the physical side effect when DB persistence fails.
            try:
                if dest_path.exists():
                    dest_path.unlink()
                if teacher_folder.exists() and not any(teacher_folder.iterdir()):
                    teacher_folder.rmdir()
            except OSError:
                pass
            raise

        self._timeline_service.log_event(
            teacher_id=teacher_id,
            event_type=TeacherTimelineEventType.DOCUMENT_UPLOADED,
            title="Document Uploaded",
            description=f"Uploaded {file_name}",
            metadata={"document_id": doc.id, "document_type": document_type}
        )
        if self._event_bus:
            self._event_bus.publish(TeacherDocumentChanged(
                teacher_id=teacher_id,
                document_id=doc.id,
                action="uploaded",
            ))
        return doc

    def get_documents_for_teacher(self, teacher_id: int) -> List[TeacherDocument]:
        with self._session_factory() as session:
            repo = TeacherDocumentRepository(session)
            return repo.get_by_teacher(teacher_id)

    def delete_document(self, document_id: int) -> None:
        # Keep the physical file until the DB delete has committed. If the DB
        # transaction fails, the DB record still points to a valid file.
        with self._session_factory() as session:
            repo = TeacherDocumentRepository(session)
            doc = repo.get_by_id(document_id)
            if doc is None:
                raise ValueError(f"Document {document_id} not found.")

            teacher_id = doc.teacher_id
            file_name = doc.file_name
            file_path = get_paths().attachment_dir / doc.file_path

            repo.delete(doc)
            session.commit()

        # Post-commit cleanup is intentionally best-effort. A failed physical
        # delete cannot corrupt DB consistency; the file becomes an orphan that
        # can be handled by runtime cleanup.
        try:
            if file_path.exists():
                file_path.unlink()
                parent = file_path.parent
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
        except OSError:
            pass

        if self._event_bus:
            self._event_bus.publish(TeacherDocumentChanged(
                teacher_id=teacher_id,
                document_id=document_id,
                action="deleted",
            ))

        self._timeline_service.log_event(
            teacher_id=teacher_id,
            event_type=TeacherTimelineEventType.DOCUMENT_DELETED,
            title="Document Deleted",
            description=f"Deleted {file_name}",
        )

