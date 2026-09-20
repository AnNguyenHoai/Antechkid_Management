# -*- coding: utf-8 -*-
import logging
from datetime import datetime, time
from typing import List, Dict, Optional, TYPE_CHECKING, Any, Tuple

if TYPE_CHECKING:
    from centermanager.services.report_policy import ReportPolicy

from sqlalchemy.orm import sessionmaker

from centermanager.models.attendance import Attendance, AttendanceStatus
from centermanager.models.timeline_event import TimelineEventType
from centermanager.services.timeline_service import TimelineService
from centermanager.services.permission_service import PermissionService
from centermanager.core.permission_guard import require_permission
from centermanager.events.student_events import StudentUpdated
from centermanager.repositories.provider import RepositoryProvider, SqlAlchemyRepositoryProvider

logger = logging.getLogger(__name__)


class AttendanceService:
    def __init__(
        self,
        session_factory: sessionmaker,
        timeline_service: TimelineService,
        permission_service: PermissionService,
        report_policy: Optional[Any] = None,
        report_service: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        repository_provider: Optional[RepositoryProvider] = None,
    ):
        self._session_factory = session_factory
        self._timeline_service = timeline_service
        self._permission_service = permission_service
        self._report_policy = report_policy
        self._report_service = report_service
        self._event_bus = event_bus
        self._repository_provider = repository_provider or SqlAlchemyRepositoryProvider()

    def _validate_status(self, status: str) -> str:
        valid = [e.value for e in AttendanceStatus]
        if status not in valid:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(valid)}")
        return status

    @staticmethod
    def _normalize_arrival_time(value: Any) -> Optional[time]:
        """Normalize UI/service input to the model's canonical ``datetime.time`` type."""
        if value is None:
            return None
        if isinstance(value, time):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            for fmt in ("%H:%M", "%H:%M:%S"):
                try:
                    return datetime.strptime(text, fmt).time()
                except ValueError:
                    continue
        raise ValueError("Arrival time must use HH:MM or HH:MM:SS.")

    def _check_student_enrolled(self, student_id: int, session_id: int) -> bool:
        with self._session_factory() as session:
            session_repo = self._repository_provider.sessions(session)
            session_obj = session_repo.get_by_id(session_id)
            if not session_obj:
                return False
            enroll_repo = self._repository_provider.enrollments(session)
            return enroll_repo.exists(student_id, session_obj.class_id)

    @require_permission("attendance.create")
    def create_or_update_attendance(
        self,
        session_id: int,
        student_id: int,
        status: str,
        arrival_time: Optional[str] = None,
        teacher_note: Optional[str] = None,
    ) -> Attendance:
        if not self._check_student_enrolled(student_id, session_id):
            raise ValueError("Student is not enrolled in this class.")
        status = self._validate_status(status)

        with self._session_factory() as session:
            repo = self._repository_provider.attendance(session)
            existing = repo.get_by_session_and_student(session_id, student_id)
            if existing:
                old_status = existing.status
                existing.status = status
                if arrival_time is not None:
                    existing.arrival_time = arrival_time
                if teacher_note is not None:
                    existing.teacher_note = teacher_note
                session.commit()
                repo.refresh(existing)

                if old_status != status:
                    self._timeline_service.log_event(
                        student_id=student_id,
                        event_type=TimelineEventType.ATTENDANCE_UPDATED,
                        title="Attendance Updated",
                        description=f"Session {session_id}: status changed from {old_status} to {status}",
                        metadata={"session_id": session_id, "old_status": old_status, "new_status": status},
                    )
                self._trigger_report_policy(student_id, session_id, status)
                return existing

            attendance = Attendance(
                session_id=session_id,
                student_id=student_id,
                status=status,
                arrival_time=arrival_time,
                teacher_note=teacher_note,
            )
            repo.add(attendance)
            session.commit()
            repo.refresh(attendance)
            self._timeline_service.log_event(
                student_id=student_id,
                event_type=TimelineEventType.ATTENDANCE_CREATED,
                title="Attendance Recorded",
                description=f"Session {session_id}: {status}",
                metadata={"session_id": session_id, "status": status},
            )
            if self._event_bus is not None:
                self._event_bus.publish(
                    StudentUpdated(student_id=student_id, student_code="", student_name="", changes=["attendance"])
                )
            return attendance

    def _trigger_report_policy(self, student_id: int, session_id: int, status: str) -> None:
        return None

    def _normalize_session_rows(
        self,
        attendance_rows: Dict[int, Dict[str, Any]],
    ) -> Dict[int, Dict[str, Any]]:
        normalized: Dict[int, Dict[str, Any]] = {}
        for raw_student_id, raw in attendance_rows.items():
            student_id = int(raw_student_id)
            if not isinstance(raw, dict):
                raise ValueError(f"Attendance row for student {student_id} must be a mapping.")
            status = self._validate_status(str(raw.get("status", "")))
            note = raw.get("teacher_note")
            if note is not None:
                note = str(note).strip() or None
            normalized[student_id] = {
                "status": status,
                "arrival_time": self._normalize_arrival_time(raw.get("arrival_time")),
                "teacher_note": note,
            }
        return normalized

    def _publish_session_save_side_effects(
        self,
        session_id: int,
        changes: List[Tuple[int, Optional[str], str]],
    ) -> None:
        """Preserve legacy timeline/report/event behavior after the atomic commit."""
        for student_id, old_status, new_status in changes:
            if old_status is None:
                self._timeline_service.log_event(
                    student_id=student_id,
                    event_type=TimelineEventType.ATTENDANCE_CREATED,
                    title="Attendance Recorded",
                    description=f"Session {session_id}: {new_status}",
                    metadata={"session_id": session_id, "status": new_status},
                )
                if self._event_bus is not None:
                    self._event_bus.publish(
                        StudentUpdated(
                            student_id=student_id,
                            student_code="",
                            student_name="",
                            changes=["attendance"],
                        )
                    )
                continue

            if old_status != new_status:
                self._timeline_service.log_event(
                    student_id=student_id,
                    event_type=TimelineEventType.ATTENDANCE_UPDATED,
                    title="Attendance Updated",
                    description=f"Session {session_id}: status changed from {old_status} to {new_status}",
                    metadata={
                        "session_id": session_id,
                        "old_status": old_status,
                        "new_status": new_status,
                    },
                )
            self._trigger_report_policy(student_id, session_id, new_status)

    def _save_session_attendance_atomic(
        self,
        session_id: int,
        attendance_rows: Dict[int, Dict[str, Any]],
    ) -> List[Attendance]:
        """Persist one Session attendance sheet with exactly one database commit."""
        normalized_rows = self._normalize_session_rows(attendance_rows)
        if not normalized_rows:
            return []

        side_effects: List[Tuple[int, Optional[str], str]] = []
        results: List[Attendance] = []

        with self._session_factory() as session:
            session_repo = self._repository_provider.sessions(session)
            enrollment_repo = self._repository_provider.enrollments(session)
            attendance_repo = self._repository_provider.attendance(session)

            try:
                session_obj = session_repo.get_by_id(session_id)
                if not session_obj:
                    raise ValueError("Session not found.")

                # Validate the complete sheet before mutating any attendance row.
                for student_id in normalized_rows:
                    if not enrollment_repo.exists(student_id, session_obj.class_id):
                        raise ValueError(
                            f"Student {student_id} is not actively enrolled in this class."
                        )

                existing_by_student = {
                    attendance.student_id: attendance
                    for attendance in attendance_repo.get_by_session(session_id)
                }

                for student_id, row in normalized_rows.items():
                    existing = existing_by_student.get(student_id)
                    if existing is not None:
                        old_status = existing.status
                        existing.status = row["status"]
                        # The session sheet is authoritative: blank UI values clear old values.
                        existing.arrival_time = row["arrival_time"]
                        existing.teacher_note = row["teacher_note"]
                        results.append(existing)
                        side_effects.append((student_id, old_status, row["status"]))
                        continue

                    attendance = Attendance(
                        session_id=session_id,
                        student_id=student_id,
                        status=row["status"],
                        arrival_time=row["arrival_time"],
                        teacher_note=row["teacher_note"],
                    )
                    attendance_repo.add(attendance)
                    results.append(attendance)
                    side_effects.append((student_id, None, row["status"]))

                session.commit()
            except Exception:
                session.rollback()
                raise

            for attendance in results:
                attendance_repo.refresh(attendance)

        self._publish_session_save_side_effects(session_id, side_effects)
        return results

    @require_permission("attendance.create")
    def save_session_attendance(
        self,
        session_id: int,
        attendance_rows: Dict[int, Dict[str, Any]],
    ) -> List[Attendance]:
        """Save all rows from the Session attendance UI as one atomic unit."""
        return self._save_session_attendance_atomic(session_id, attendance_rows)

    @require_permission("attendance.create")
    def batch_update_attendance(
        self,
        session_id: int,
        student_statuses: Dict[int, str],
        arrival_time: Optional[str] = None,
        teacher_note: Optional[str] = None,
    ) -> List[Attendance]:
        # Backward-compatible API: translate the legacy shared values into the
        # canonical per-student sheet and use the same atomic transaction.
        attendance_rows = {
            student_id: {
                "status": status,
                "arrival_time": arrival_time,
                "teacher_note": teacher_note,
            }
            for student_id, status in student_statuses.items()
        }
        return self._save_session_attendance_atomic(session_id, attendance_rows)

    @require_permission("attendance.view")
    def get_attendance_for_session(self, session_id: int) -> List[Attendance]:
        with self._session_factory() as session:
            return self._repository_provider.attendance(session).get_by_session(session_id)

    @require_permission("attendance.view")
    def get_attendance_for_student(self, student_id: int) -> List[Attendance]:
        with self._session_factory() as session:
            return self._repository_provider.attendance(session).get_by_student(student_id)

    @require_permission("attendance.view")
    def get_summary_for_session(self, session_id: int) -> Dict[str, int]:
        with self._session_factory() as session:
            return self._repository_provider.attendance(session).get_summary_by_session(session_id)

    @require_permission("attendance.view")
    def get_attendance_rate_for_student(self, student_id: int) -> float:
        with self._session_factory() as session:
            attendances = self._repository_provider.attendance(session).get_by_student(student_id)
            if not attendances:
                return 0.0
            present_count = sum(1 for a in attendances if a.status == AttendanceStatus.PRESENT.value)
            return (present_count / len(attendances)) * 100
