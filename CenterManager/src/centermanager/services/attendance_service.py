# -*- coding: utf-8 -*-
import logging
from typing import List, Dict, Optional, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from centermanager.services.report_policy import ReportPolicy

from sqlalchemy.orm import sessionmaker

from centermanager.models.attendance import Attendance, AttendanceStatus
from centermanager.models.timeline_event import TimelineEventType
from centermanager.repositories.attendance_repository import AttendanceRepository
from centermanager.repositories.enrollment_repository import EnrollmentRepository
from centermanager.services.timeline_service import TimelineService
from centermanager.services.permission_service import PermissionService
from centermanager.core.permission_guard import require_permission
from centermanager.events.student_events import StudentUpdated

logger = logging.getLogger(__name__)


class AttendanceService:
    def __init__(
        self,
        session_factory: sessionmaker,
        timeline_service: TimelineService,
        permission_service: PermissionService,
        report_policy: Optional[Any] = None,    # ReportPolicy instance, can be None
        report_service: Optional[Any] = None,   # ReportService instance, can be None
        event_bus: Optional[Any] = None,
    ):
        self._session_factory = session_factory
        self._timeline_service = timeline_service
        self._permission_service = permission_service
        self._report_policy = report_policy
        self._report_service = report_service
        self._event_bus = event_bus

    def _validate_status(self, status: str) -> str:
        valid = [e.value for e in AttendanceStatus]
        if status not in valid:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(valid)}")
        return status

    def _check_student_enrolled(self, student_id: int, session_id: int) -> bool:
        """Check if student is enrolled in the class of the session."""
        with self._session_factory() as session:
            # Lấy class_id từ session
            from centermanager.repositories.session_repository import SessionRepository
            session_repo = SessionRepository(session)
            session_obj = session_repo.get_by_id(session_id)
            if not session_obj:
                return False
            class_id = session_obj.class_id
            enroll_repo = EnrollmentRepository(session)
            return enroll_repo.exists(student_id, class_id)

    @require_permission("attendance.create")
    def create_or_update_attendance(
        self,
        session_id: int,
        student_id: int,
        status: str,
        arrival_time: Optional[str] = None,
        teacher_note: Optional[str] = None
    ) -> Attendance:
        # Validate student enrolled
        if not self._check_student_enrolled(student_id, session_id):
            raise ValueError("Student is not enrolled in this class.")

        status = self._validate_status(status)

        with self._session_factory() as session:
            repo = AttendanceRepository(session)
            existing = repo.get_by_session_and_student(session_id, student_id)

            if existing:
                old_status = existing.status
                existing.status = status
                if arrival_time is not None:
                    existing.arrival_time = arrival_time
                if teacher_note is not None:
                    existing.teacher_note = teacher_note
                session.commit()
                session.refresh(existing)

                if old_status != status:
                    self._timeline_service.log_event(
                        student_id=student_id,
                        event_type=TimelineEventType.ATTENDANCE_UPDATED,
                        title="Attendance Updated",
                        description=f"Session {session_id}: status changed from {old_status} to {status}",
                        metadata={"session_id": session_id, "old_status": old_status, "new_status": status}
                    )

                # Trigger report policy
                self._trigger_report_policy(student_id, session_id, status)

                return existing
            else:
                attendance = Attendance(
                    session_id=session_id,
                    student_id=student_id,
                    status=status,
                    arrival_time=arrival_time,
                    teacher_note=teacher_note
                )
                repo.add(attendance)
                session.commit()
                session.refresh(attendance)

                self._timeline_service.log_event(
                    student_id=student_id,
                    event_type=TimelineEventType.ATTENDANCE_CREATED,
                    title="Attendance Recorded",
                    description=f"Session {session_id}: {status}",
                    metadata={"session_id": session_id, "status": status}
                )

                # Attendance is report-relevant student data. Generation is
                # deferred until Finish Editing publishes successfully.
                if self._event_bus is not None:
                    self._event_bus.publish(
                        StudentUpdated(student_id=student_id, student_code="", student_name="", changes=["attendance"])
                    )

                return attendance
    def _trigger_report_policy(self, student_id: int, session_id: int, status: str) -> None:
        """Deprecated compatibility hook; generation is deferred to publish lifecycle."""
        return None

    @require_permission("attendance.create")
    def batch_update_attendance(
        self,
        session_id: int,
        student_statuses: Dict[int, str],  # student_id -> status
        arrival_time: Optional[str] = None,
        teacher_note: Optional[str] = None
    ) -> List[Attendance]:
        """Update multiple students' attendance for a session."""
        results = []
        for student_id, status in student_statuses.items():
            att = self.create_or_update_attendance(
                session_id, student_id, status, arrival_time, teacher_note
            )
            results.append(att)
        return results

    @require_permission("attendance.view")
    def get_attendance_for_session(self, session_id: int) -> List[Attendance]:
        with self._session_factory() as session:
            repo = AttendanceRepository(session)
            return repo.get_by_session(session_id)

    @require_permission("attendance.view")
    def get_attendance_for_student(self, student_id: int) -> List[Attendance]:
        with self._session_factory() as session:
            repo = AttendanceRepository(session)
            return repo.get_by_student(student_id)

    @require_permission("attendance.view")
    def get_summary_for_session(self, session_id: int) -> Dict[str, int]:
        with self._session_factory() as session:
            repo = AttendanceRepository(session)
            return repo.get_summary_by_session(session_id)

    @require_permission("attendance.view")
    def get_attendance_rate_for_student(self, student_id: int) -> float:
        """Return attendance rate as percentage (0-100)."""
        with self._session_factory() as session:
            repo = AttendanceRepository(session)
            attendances = repo.get_by_student(student_id)
            if not attendances:
                return 0.0
            present_count = sum(1 for a in attendances if a.status == AttendanceStatus.PRESENT.value)
            return (present_count / len(attendances)) * 100