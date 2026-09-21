# -*- coding: utf-8 -*-
import logging
from datetime import datetime, time
from typing import List, Dict, Optional, TYPE_CHECKING, Any, Tuple

if TYPE_CHECKING:
    from centermanager.services.report_policy import ReportPolicy

from sqlalchemy.orm import sessionmaker

from centermanager.models.attendance import Attendance, AttendanceStatus
from centermanager.models.student import Student
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

    @staticmethod
    def _enrollment_covers_session_date(enrollment: Any, scheduled_date: Any) -> bool:
        """Return whether an enrollment owned the student/class relationship on a Session date."""
        if scheduled_date is None:
            return False
        if enrollment.start_date is not None and enrollment.start_date > scheduled_date:
            return False
        if enrollment.end_date is not None and enrollment.end_date < scheduled_date:
            return False
        return True

    def _is_student_eligible_for_session(
        self,
        enrollment_repo: Any,
        student_id: int,
        class_id: int,
        scheduled_date: Any,
    ) -> bool:
        """Use historical Enrollment dates when available, with legacy provider compatibility."""
        history_getter = getattr(enrollment_repo, "get_by_student_and_class", None)
        if scheduled_date is not None and callable(history_getter):
            enrollments = history_getter(student_id, class_id)
            return any(
                self._enrollment_covers_session_date(enrollment, scheduled_date)
                for enrollment in enrollments
            )

        # Compatibility for lightweight injected providers that expose the older
        # ``exists`` seam only. Production repositories take the historical path.
        exists = getattr(enrollment_repo, "exists", None)
        return bool(callable(exists) and exists(student_id, class_id))

    def _check_student_enrolled(self, student_id: int, session_id: int) -> bool:
        with self._session_factory() as session:
            session_repo = self._repository_provider.sessions(session)
            session_obj = session_repo.get_by_id(session_id)
            if not session_obj:
                return False
            enroll_repo = self._repository_provider.enrollments(session)
            return self._is_student_eligible_for_session(
                enroll_repo,
                student_id,
                session_obj.class_id,
                getattr(session_obj, "scheduled_date", None),
            )

    @require_permission("attendance.create")
    def create_or_update_attendance(
        self,
        session_id: int,
        student_id: int,
        status: str,
        arrival_time: Optional[str] = None,
        teacher_note: Optional[str] = None,
    ) -> Attendance:
        """Backward-compatible single-row API routed through the atomic mutation boundary."""
        saved = self._save_session_attendance_atomic(
            session_id,
            {
                student_id: {
                    "status": status,
                    "arrival_time": arrival_time,
                    "teacher_note": teacher_note,
                }
            },
            preserve_existing_optional_fields=True,
        )
        if not saved:
            raise RuntimeError("Attendance save did not return a record.")
        return saved[0]

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
        preserve_existing_optional_fields: bool = False,
    ) -> List[Attendance]:
        """Persist attendance rows with exactly one database commit.

        Session-sheet callers are authoritative and may clear optional values.
        The legacy single-row API can preserve existing optional fields when its
        historical ``None`` defaults mean "not supplied" rather than "clear".
        """
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

                # Validate every requested row against the roster that belonged to
                # this class on the Session date, not only today's ACTIVE roster.
                for student_id in normalized_rows:
                    if not self._is_student_eligible_for_session(
                        enrollment_repo,
                        student_id,
                        session_obj.class_id,
                        getattr(session_obj, "scheduled_date", None),
                    ):
                        raise ValueError(
                            f"Student {student_id} is not enrolled in this class for this session date."
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
                        if preserve_existing_optional_fields:
                            if row["arrival_time"] is not None:
                                existing.arrival_time = row["arrival_time"]
                            if row["teacher_note"] is not None:
                                existing.teacher_note = row["teacher_note"]
                        else:
                            # The Session sheet is authoritative: blank UI values clear old values.
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
        """Save a complete Session attendance sheet as one atomic unit."""
        roster_ids = {student.id for student in self._get_roster_for_session(session_id)}
        payload_ids = {int(student_id) for student_id in attendance_rows}
        if payload_ids != roster_ids:
            missing_ids = sorted(roster_ids - payload_ids)
            unexpected_ids = sorted(payload_ids - roster_ids)
            details = []
            if missing_ids:
                details.append(f"missing student(s): {', '.join(map(str, missing_ids))}")
            if unexpected_ids:
                details.append(f"unexpected student(s): {', '.join(map(str, unexpected_ids))}")
            raise ValueError(
                "Attendance sheet must contain exactly one marked row for every student in the session roster"
                + (f" ({'; '.join(details)})" if details else "")
                + "."
            )
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

    def _get_roster_for_session(self, session_id: int) -> List[Student]:
        """Resolve the canonical historical roster without adding another permission boundary."""
        with self._session_factory() as session:
            session_obj = self._repository_provider.sessions(session).get_by_id(session_id)
            if not session_obj:
                raise ValueError("Session not found.")
            enrollments = self._repository_provider.enrollments(session).get_by_class_with_student(
                session_obj.class_id
            )
            scheduled_date = getattr(session_obj, "scheduled_date", None)
            if scheduled_date is None:
                return [
                    enrollment.student
                    for enrollment in enrollments
                    if enrollment.student is not None
                    and getattr(enrollment, "status", None) == "ACTIVE"
                ]
            return [
                enrollment.student
                for enrollment in enrollments
                if enrollment.student is not None
                and self._enrollment_covers_session_date(enrollment, scheduled_date)
            ]

    @require_permission("attendance.view")
    def get_roster_for_session(self, session_id: int) -> List[Student]:
        """Return students whose Enrollment covered the Session scheduled date."""
        return self._get_roster_for_session(session_id)

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
    def get_session_attendance_overview(self, session_id: int) -> Dict[str, Any]:
        """Return one roster-aware Session summary used by all Attendance surfaces."""
        roster = self._get_roster_for_session(session_id)
        with self._session_factory() as session:
            summary = self._repository_provider.attendance(session).get_summary_by_session(session_id)
        roster_total = len(roster)
        recorded = sum(summary.values())
        unmarked = max(roster_total - recorded, 0)
        present = summary.get(AttendanceStatus.PRESENT.value, 0)
        attendance_rate = (present / roster_total * 100) if roster_total > 0 else 0.0
        return {
            **summary,
            "RosterTotal": roster_total,
            "Recorded": recorded,
            "Unmarked": unmarked,
            "AttendanceRate": attendance_rate,
        }

    @require_permission("attendance.view")
    def get_attendance_rate_for_student(self, student_id: int) -> float:
        with self._session_factory() as session:
            attendances = self._repository_provider.attendance(session).get_by_student(student_id)
            if not attendances:
                return 0.0
            present_count = sum(1 for a in attendances if a.status == AttendanceStatus.PRESENT.value)
            return (present_count / len(attendances)) * 100
