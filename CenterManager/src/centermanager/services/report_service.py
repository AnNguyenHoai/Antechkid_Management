# -*- coding: utf-8 -*-
"""
ReportService - entry point for generating all reports.
Supports both manual and automatic generation with history.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from centermanager.core.paths import get_paths
from centermanager.core.current_user import get_current_user
from centermanager.models.report import Report
from centermanager.repositories.report_repository import ReportRepository
from centermanager.services.student_service import StudentService
from centermanager.services.parent_service import ParentService
from centermanager.services.attendance_service import AttendanceService
from centermanager.services.session_service import SessionService
from centermanager.services.student_note_service import StudentNoteService
from centermanager.services.outstanding_service import OutstandingService
from centermanager.services.income_service import IncomeService
from centermanager.export.pdf.student_report_generator import StudentReportGenerator

logger = logging.getLogger(__name__)


class ReportService:
    def __init__(
        self,
        student_service: StudentService,
        parent_service: ParentService,
        attendance_service: AttendanceService,
        session_service: SessionService,
        student_note_service: StudentNoteService,
        outstanding_service: OutstandingService,
        income_service: IncomeService,
        session_factory,
    ) -> None:
        self._student_service = student_service
        self._parent_service = parent_service
        self._attendance_service = attendance_service
        self._session_service = session_service
        self._student_note_service = student_note_service
        self._outstanding_service = outstanding_service
        self._income_service = income_service
        self._session_factory = session_factory

        self._generator = StudentReportGenerator(
            student_service,
            parent_service,
            attendance_service,
            session_service,
            student_note_service,
            outstanding_service,
            income_service,
        )

    def generate_student_report(
        self,
        student_id: int,
        report_type: str = "manual",
        trigger_event: Optional[str] = None,
        generated_by: Optional[str] = None,
        output_path: Optional[Path] = None,
    ) -> Path:
        """
        Generate a PDF report and save metadata to database.
        """
        student = self._student_service.get_student_with_relations(student_id)

        if output_path is None:
            reports_root = get_paths().runtime_root / "Reports" / "Student" / student.student_code
            reports_root.mkdir(parents=True, exist_ok=True)
            # One student owns one materialized latest profile report.
            output_path = reports_root / "StudentProfile.pdf"

        # Generate to a temporary file first, then atomically replace the
        # current report so a failed generation never destroys the last good PDF.
        temp_path = output_path.with_suffix(".tmp.pdf")
        try:
            file_path = self._generator.generate(student_id, temp_path)
            file_path.replace(output_path)
            file_path = output_path
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)

        # Save metadata (replace existing singleton record)
        with self._session_factory() as session:
            repo = ReportRepository(session)
            metadata = {
                "center_name": "AN TECHKIDS",
                "academic_year": "2026-2027",
            }
            for existing in repo.get_by_student(student_id):
                repo.delete(existing)
            report = Report(
                student_id=student_id,
                file_path=str(file_path.relative_to(get_paths().runtime_root)),
                report_type=report_type,
                trigger_event=trigger_event,
                generated_by=generated_by or (get_current_user().full_name if get_current_user() else "system"),
                generated_at=datetime.now(),
                metadata_json=json.dumps(metadata, ensure_ascii=False),
            )
            repo.add(report)
            session.commit()
            session.refresh(report)

        logger.info(f"Student report generated for student {student_id}: {file_path}")
        return file_path

    def get_student_reports(self, student_id: int) -> List[Report]:
        with self._session_factory() as session:
            repo = ReportRepository(session)
            return repo.get_by_student(student_id)

    def get_report_file_path(self, report_id: int) -> Optional[Path]:
        with self._session_factory() as session:
            repo = ReportRepository(session)
            report = repo.get_by_id(report_id)
            if report is None:
                return None
            return get_paths().runtime_root / report.file_path

    def delete_report(self, report_id: int) -> None:
        with self._session_factory() as session:
            repo = ReportRepository(session)
            report = repo.get_by_id(report_id)
            if report is None:
                return
            file_path = get_paths().runtime_root / report.file_path
            if file_path.exists():
                file_path.unlink()
            repo.delete(report)
            session.commit()

    def report_exists(self, student_id: int, trigger_event: str) -> bool:
        """Check if a report with given trigger already exists for this student."""
        with self._session_factory() as session:
            repo = ReportRepository(session)
            return repo.get_by_student_and_trigger(student_id, trigger_event) is not None

    def report_exists_on_date(self, student_id: int, trigger_event: str, target_date) -> bool:
        """Check whether this student already has this trigger's report on target_date."""
        with self._session_factory() as session:
            repo = ReportRepository(session)
            return repo.exists_for_student_trigger_on_date(
                student_id, trigger_event, target_date
            )

