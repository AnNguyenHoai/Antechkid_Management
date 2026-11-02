"""A-02: read-only monthly attendance exception projection.

Recorded coverage and student presence are distinct measures.
Historical eligibility is delegated to the A-01 session roster contract.
"""
from __future__ import annotations

import csv
import io
import calendar
from collections import defaultdict
from datetime import date
from typing import Optional

from centermanager.core.clock import get_clock
from centermanager.models.session import SessionStatus
from centermanager.models.attendance import AttendanceStatus
from centermanager.repositories.provider import RepositoryProvider, SqlAlchemyRepositoryProvider
from centermanager.services.attendance_service import AttendanceService


class MonthlyAttendanceExceptionService:
    """Read-only view; never creates attendance or changes historical records."""

    def __init__(self, session_factory, repository_provider: RepositoryProvider | None = None):
        self._session_factory = session_factory
        self._repository_provider = repository_provider or SqlAlchemyRepositoryProvider()

    @staticmethod
    def _is_due(session_obj, cutoff: date) -> bool:
        if session_obj.status in (SessionStatus.CANCELLED.value, SessionStatus.POSTPONED.value):
            return False
        occurred = session_obj.actual_date or session_obj.scheduled_date
        return occurred is not None and occurred <= cutoff

    def list_rows(
        self, *, year: int, month: int, class_id: Optional[int] = None,
        minimum_rate: float = 80.0, as_of_date: Optional[date] = None,
        issue: str = "ALL", include_all: bool = False,
    ) -> list[dict]:
        if not 1 <= month <= 12 or not 2000 <= year <= 2100:
            raise ValueError("Invalid reporting month")
        if not 0 <= minimum_rate <= 100:
            raise ValueError("Rate threshold must be 0..100")
        if issue not in {"ALL", "LOW_ATTENDANCE", "MISSING_RECORDS"}:
            raise ValueError("Unsupported exception filter")
        first = date(year, month, 1)
        last = date(year, month, calendar.monthrange(year, month)[1])
        cutoff = min(last, as_of_date or get_clock().today())
        if cutoff < first:
            return []

        with self._session_factory() as db:
            sessions = self._repository_provider.sessions(db).list_monthly_for_attendance(
                first, last, class_id=class_id
            )
            class_ids = {item.class_id for item in sessions}
            if not class_ids:
                return []
            enrollments = self._repository_provider.enrollments(db).list_monthly_roster_candidates(class_ids)
            by_class = defaultdict(list)
            for item in enrollments:
                by_class[item.class_id].append(item)
            session_ids = [item.id for item in sessions]
            attendances = self._repository_provider.attendance(db).list_for_session_ids(session_ids)
            recorded = defaultdict(dict)
            for entry in attendances:
                recorded[entry.session_id][entry.student_id] = entry.status

            aggregates = {}
            for lesson in sessions:
                if not self._is_due(lesson, cutoff):
                    continue
                roster = AttendanceService._roster_students_for_session(
                    by_class[lesson.class_id], lesson
                )
                for student in roster:
                    key = (lesson.class_id, student.id)
                    row = aggregates.setdefault(key, {
                        "student_id": student.id, "student_code": student.student_code or "",
                        "student_name": student.full_name or "",
                        "class_id": lesson.class_id,
                        "class_name": lesson.class_.name if lesson.class_ is not None else "",
                        "required": 0, "recorded": 0, "present": 0,
                        "late": 0, "absent": 0, "excused": 0,
                    })
                    row["required"] += 1
                    status = recorded[lesson.id].get(student.id)
                    if status is None:
                        continue
                    row["recorded"] += 1
                    if status == AttendanceStatus.PRESENT.value:
                        row["present"] += 1
                    elif status == AttendanceStatus.LATE.value:
                        row["late"] += 1
                    elif status == AttendanceStatus.ABSENT.value:
                        row["absent"] += 1
                    elif status == AttendanceStatus.EXCUSED.value:
                        row["excused"] += 1

        results = []
        for row in aggregates.values():
            due = row["required"]
            row["missing"] = due - row["recorded"]
            row["attendance_rate"] = round(row["present"] / due * 100, 2)
            row["recording_rate"] = round(row["recorded"] / due * 100, 2)
            is_low = row["attendance_rate"] < minimum_rate
            is_missing = row["missing"] > 0
            if not include_all and (issue == "ALL" and not (is_low or is_missing)
                    or issue == "LOW_ATTENDANCE" and not is_low
                    or issue == "MISSING_RECORDS" and not is_missing):
                continue
            results.append(row)
        return sorted(results, key=lambda row: (row["class_name"].casefold(), row["student_name"].casefold(), row["student_id"]))

    @staticmethod
    def to_csv(rows: list[dict]) -> str:
        stream = io.StringIO(newline="")
        columns = [
            ("student_code", "Student Code"), ("student_name", "Student"),
            ("class_name", "Class"), ("required", "Due Sessions"),
            ("recorded", "Recorded"), ("present", "Present"),
            ("late", "Late"), ("absent", "Absent"), ("excused", "Excused"),
            ("missing", "Missing Records"), ("attendance_rate", "Attendance Rate (%)"),
            ("recording_rate", "Recording Completeness (%)"),
        ]
        writer = csv.writer(stream)
        writer.writerow([header for _, header in columns])
        for row in rows:
            writer.writerow([row[key] for key, _ in columns])
        return stream.getvalue()
