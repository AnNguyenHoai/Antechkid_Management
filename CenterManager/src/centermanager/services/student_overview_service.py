"""S-01 Student overview read model (no persistence mutations).

Attendance coverage is available for every eligible student/class, including
students with no exception. Receivables remain contract-scoped until aggregated
per student; credits never offset other contracts.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from centermanager.core.clock import get_clock
from centermanager.repositories.provider import RepositoryProvider, SqlAlchemyRepositoryProvider
from centermanager.services.monthly_attendance_exception_service import MonthlyAttendanceExceptionService
from centermanager.services.outstanding_service import OutstandingService


class StudentOverviewService:
    def __init__(self, session_factory, outstanding_service: OutstandingService,
                 repository_provider=None):
        self._session_factory = session_factory
        self._repository_provider = repository_provider or SqlAlchemyRepositoryProvider()
        self._outstanding = outstanding_service
        self._attendance = MonthlyAttendanceExceptionService(session_factory, self._repository_provider)

    @staticmethod
    def compose(students, attendance_rows, debt_rows, active_classes=None):
        active_classes = active_classes or {}
        attendance_by_student = defaultdict(list)
        for row in attendance_rows:
            attendance_by_student[row["student_id"]].append(row)
        debt_by_student = defaultdict(int)
        for debt in debt_rows:
            debt_by_student[debt.student_id] += int(debt.debt_amount)
        result = []
        for student in students:
            attendance = attendance_by_student[student.id]
            due = sum(row["required"] for row in attendance)
            present = sum(row["present"] for row in attendance)
            missing = sum(row["missing"] for row in attendance)
            absent = sum(row["absent"] for row in attendance)
            result.append({
                "student_id": student.id,
                "student_code": student.student_code,
                "student_name": student.full_name,
                "status": student.status,
                "classes": ", ".join(sorted(active_classes.get(student.id, set()))),
                "monthly_classes": ", ".join(sorted({row["class_name"] for row in attendance})),
                "due": due, "present": present, "absent": absent, "missing": missing,
                "attendance_rate": round(present * 100 / due, 1) if due else None,
                "debt": debt_by_student[student.id],
            })
        return result

    def list_rows(self, *, year: int, month: int, as_of_date: date | None = None):
        cutoff = as_of_date or get_clock().today()
        with self._session_factory() as db:
            active_classes = defaultdict(set)
            enrollments, _ = self._repository_provider.enrollments(db).list_for_outstanding(limit=None)
            for enrollment in enrollments:
                if (enrollment.status == "ACTIVE" and enrollment.class_ is not None
                        and enrollment.class_.deleted_at is None):
                    active_classes[enrollment.student_id].add(enrollment.class_.name)
            students = [student for student in
                        self._repository_provider.students(db).list_all_including_deleted()
                        if student.deleted_at is None]
        attendance = self._attendance.list_rows(
            year=year, month=month, as_of_date=cutoff,
            minimum_rate=100, issue="ALL", include_all=True,
        )
        debt_rows, _, _ = self._outstanding.get_outstanding_page(
            view=OutstandingService.VIEW_OPEN_RECEIVABLES,
            on_date=cutoff, as_of_date=cutoff, limit=None,
        )
        return self.compose(students, attendance, debt_rows, active_classes)
