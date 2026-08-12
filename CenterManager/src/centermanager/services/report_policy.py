# -*- coding: utf-8 -*-
"""
ReportPolicy - determines when to automatically generate reports.
"""
import logging
from typing import Optional, List, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from centermanager.services.attendance_service import AttendanceService

from centermanager.services.student_service import StudentService
from centermanager.services.session_service import SessionService
from centermanager.services.class_service import ClassService
from centermanager.services.report_service import ReportService

logger = logging.getLogger(__name__)


class ReportPolicy:
    def __init__(
        self,
        student_service: StudentService,
        session_service: SessionService,
        class_service: ClassService,
        attendance_service: Any,  # type: ignore  # will be AttendanceService at runtime
        report_service: ReportService,
    ):
        self._student_service = student_service
        self._session_service = session_service
        self._class_service = class_service
        self._attendance_service = attendance_service
        self._report_service = report_service

    def check_and_trigger(self, student_id: int, event_type: str, event_data: Optional[dict] = None) -> List[str]:
        """
        Check if any report should be generated based on event.
        Returns list of trigger events that should generate a report.
        """
        logger.info(f"[POLICY] check_and_trigger called with event_type={event_type}, event_data={event_data}")
        triggers = []

        if event_type in ("attendance_updated", "session_completed"):
            progress = self._get_course_progress(student_id)
            if 50 <= progress < 100:
                if not self._report_service.report_exists(student_id, "progress_50"):
                    triggers.append("progress_50")
            elif progress >= 100:
                if not self._report_service.report_exists(student_id, "progress_100"):
                    triggers.append("progress_100")

        elif event_type == "student_updated":
            changes = event_data.get("changes", []) if event_data else []
            if changes:
                logger.info(f"[POLICY] student_updated with changes: {changes}, adding trigger")
                triggers.append("student_updated")
            else:
                logger.info(f"[POLICY] student_updated but no changes, skipping trigger")

        logger.info(f"[POLICY] Returning triggers: {triggers}")
        return triggers

    def _get_course_progress(self, student_id: int) -> float:
        """Calculate overall progress based on completed sessions vs total sessions."""
        try:
            student = self._student_service.get_student_with_relations(student_id)
            if not student.enrollments:
                return 0.0

            total_sessions = 0
            completed_sessions = 0

            for enrollment in student.enrollments:
                cls = enrollment.class_
                if cls is None:
                    continue
                sessions = self._session_service.get_sessions_for_class(cls.id)
                total_sessions += len(sessions)
                for sess in sessions:
                    attendances = self._attendance_service.get_attendance_for_session(sess.id)
                    for att in attendances:
                        if att.student_id == student_id and att.status == "Present":
                            completed_sessions += 1
                            break

            if total_sessions == 0:
                return 0.0
            return (completed_sessions / total_sessions) * 100
        except Exception as e:
            logger.exception(f"Error calculating progress for student {student_id}: {e}")
            return 0.0