"""A-01: Attendance ratios use one canonical session roster.

No production database, schema migration, or historical attendance rewrite.
"""
from datetime import date
from types import SimpleNamespace

from centermanager.models.session import SessionStatus
from centermanager.services.attendance_service import AttendanceService


def student(sid, status="ACTIVE"):
    return SimpleNamespace(id=sid, status=status)


def enrollment(st, start=1, end=12, withdrawn=None):
    return SimpleNamespace(
        student=st, start_date=date(2026, 1, 1), end_date=None,
        enrolled_from_session=start, enrolled_until_session=end,
        withdrawn_from_session=withdrawn, status="ACTIVE",
    )


def lesson(number, status=SessionStatus.SCHEDULED.value):
    return SimpleNamespace(
        class_id=1, session_number=number, status=status,
        scheduled_date=date(2026, 6, 1), actual_date=None,
    )


def marked(sid, status):
    return SimpleNamespace(student_id=sid, status=status)


def test_archived_student_is_not_current_session_denominator():
    students = [enrollment(student(1)), enrollment(student(2, "ARCHIVED")),
                enrollment(student(3))]
    roster = AttendanceService._roster_students_for_session(students, lesson(6))
    assert [s.id for s in roster] == [1, 3]
    view = AttendanceService._summary_for_roster(roster, [
        marked(1, "Present"), marked(2, "Absent"), marked(3, "Present")
    ])
    assert (view["RosterTotal"], view["Recorded"], view["Unmarked"]) == (2, 2, 0)
    assert view["AttendanceRate"] == 100
    assert view["ExcludedRecords"] == 1
    assert view.get("Absent", 0) == 0


def test_withdrawn_student_excluded_only_from_sessions_after_withdrawal():
    students = [enrollment(student(1)), enrollment(student(2), withdrawn=6)]
    before = AttendanceService._roster_students_for_session(students, lesson(5))
    after = AttendanceService._roster_students_for_session(students, lesson(6))
    assert [s.id for s in before] == [1, 2]
    assert [s.id for s in after] == [1]


def test_completed_historical_session_keeps_later_archived_student():
    students = [enrollment(student(1)), enrollment(student(2, "ARCHIVED"))]
    roster = AttendanceService._roster_students_for_session(
        students, lesson(4, SessionStatus.COMPLETED.value)
    )
    assert [s.id for s in roster] == [1, 2]
    view = AttendanceService._summary_for_roster(roster, [
        marked(1, "Present"), marked(2, "Absent")
    ])
    assert view["RosterTotal"] == 2
    assert view["AttendanceRate"] == 50


def test_duplicate_enrollments_do_not_duplicate_student_denominator():
    roster = AttendanceService._roster_students_for_session(
        [enrollment(student(1)), enrollment(student(1)), enrollment(student(2))],
        lesson(3),
    )
    assert [s.id for s in roster] == [1, 2]


def test_orphan_or_duplicate_attendance_records_cannot_inflate_rate():
    roster = [student(1), student(2)]
    view = AttendanceService._summary_for_roster(roster, [
        marked(1, "Present"), marked(1, "Present"), marked(88, "Present")
    ])
    assert view["RosterTotal"] == 2
    assert view["Recorded"] == 1
    assert view["Unmarked"] == 1
    assert view["ExcludedRecords"] == 2
    assert view["AttendanceRate"] == 50


def test_empty_roster_zero_rate_even_with_legacy_records():
    view = AttendanceService._summary_for_roster([], [marked(44, "Present")])
    assert view["RosterTotal"] == 0
    assert view["Recorded"] == 0
    assert view["AttendanceRate"] == 0
    assert view["ExcludedRecords"] == 1


def test_session_number_range_excludes_student_who_joined_later():
    roster = AttendanceService._roster_students_for_session(
        [enrollment(student(1), start=1), enrollment(student(2), start=5)],
        lesson(3, SessionStatus.COMPLETED.value),
    )
    assert [s.id for s in roster] == [1]
