# -*- coding: utf-8 -*-
"""Manual latest-only PDF export service for a single class lesson/session."""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Optional

from centermanager.core.paths import get_paths
from centermanager.export.pdf.session_report_generator import SessionReportGenerator
from centermanager.services.session_service import SessionService
from centermanager.services.session_note_service import SessionNoteService
from centermanager.services.attendance_service import AttendanceService
from centermanager.services.class_service import ClassService
from centermanager.services.student_highlight_service import StudentHighlightService
from centermanager.repositories.teacher_repository import TeacherRepository

logger = logging.getLogger(__name__)


class SessionReportService:
    def __init__(
        self,
        session_service: SessionService,
        note_service: SessionNoteService,
        attendance_service: AttendanceService,
        class_service: ClassService,
        highlight_service: Optional[StudentHighlightService] = None,
        generator: Optional[SessionReportGenerator] = None,
    ) -> None:
        self._session_service = session_service
        self._note_service = note_service
        self._attendance_service = attendance_service
        self._class_service = class_service
        self._highlight_service = highlight_service
        self._generator = generator or SessionReportGenerator()

    @staticmethod
    def _safe_folder_name(value: str, fallback: str) -> str:
        """Keep export paths human-readable and safe on Windows/macOS/Linux."""
        value = (value or "").strip()
        value = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value)
        value = re.sub(r"\s+", " ", value).strip(" ._")
        return value or fallback

    def _resolve_teacher_name(self, session, class_obj) -> str:
        """Prefer the historical teacher recorded on the Session.

        Class assignments are current-state data and may change after the
        session took place, so they are only a compatibility fallback.
        """
        if getattr(session, "teacher_id", None):
            session_factory = getattr(self._session_service, "_session_factory", None)
            if session_factory is not None:
                try:
                    with session_factory() as db_session:
                        teacher = TeacherRepository(db_session).get_by_id(session.teacher_id)
                        if teacher is not None and getattr(teacher, "full_name", None):
                            return teacher.full_name
                except Exception:
                    logger.warning(
                        "Unable to resolve historical teacher for session_id=%s teacher_id=%s",
                        getattr(session, "id", None),
                        session.teacher_id,
                        exc_info=True,
                    )

        teachers = ", ".join(
            t.full_name
            for t in getattr(class_obj, "teachers", [])
            if getattr(t, "full_name", None)
        )
        return teachers or (getattr(class_obj, "teacher", "") or "")

    def get_output_path(self, session_id: int) -> Path:
        session = self._session_service.get_session(session_id)
        class_obj = self._class_service.get_class_with_details(session.class_id)

        class_name = self._safe_folder_name(
            f"Class_{class_obj.id}_{class_obj.name}",
            f"Class_{class_obj.id}",
        )
        lesson_title = self._safe_folder_name(
            session.title or session.lesson_topic or "",
            f"Lesson_{session.session_number}",
        )
        lesson_name = self._safe_folder_name(
            f"Lesson_{session.session_number}_{lesson_title}",
            f"Lesson_{session.session_number}",
        )

        return (
            get_paths().session_report_dir
            / class_name
            / lesson_name
            / "latest.pdf"
        )

    def get_output_directory(self, session_id: int) -> Path:
        return self.get_output_path(session_id).parent

    def generate_session_report(self, session_id: int) -> Path:
        session = self._session_service.get_session(session_id)
        class_obj = self._class_service.get_class_with_details(session.class_id)
        note = self._note_service.get_note(session_id)
        attendance_summary = self._attendance_service.get_summary_for_session(session_id)
        teacher_name = self._resolve_teacher_name(session, class_obj)
        highlights = (
            self._highlight_service.get_highlights_for_session(session_id)
            if self._highlight_service is not None
            else []
        )

        # Build from already loaded domain objects to keep the generated path
        # grouped by the actual class and lesson/session.
        class_name = self._safe_folder_name(
            f"Class_{class_obj.id}_{class_obj.name}",
            f"Class_{class_obj.id}",
        )
        lesson_title = self._safe_folder_name(
            session.title or session.lesson_topic or "",
            f"Lesson_{session.session_number}",
        )
        lesson_name = self._safe_folder_name(
            f"Lesson_{session.session_number}_{lesson_title}",
            f"Lesson_{session.session_number}",
        )
        output_path = (
            get_paths().session_report_dir
            / class_name
            / lesson_name
            / "latest.pdf"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Latest-only lifecycle: generator writes to a temporary file first.
        temp_path = output_path.with_suffix(".tmp.pdf")
        if temp_path.exists():
            temp_path.unlink()
        self._generator.generate(temp_path, {
            "session": session,
            "class": class_obj,
            "note": note,
            "attendance_summary": attendance_summary,
            "teacher_name": teacher_name,
            "highlights": highlights,
        })
        os.replace(temp_path, output_path)
        logger.info(
            "Session report generated: session_id=%s class_id=%s path=%s",
            session_id, session.class_id, output_path,
        )
        return output_path
