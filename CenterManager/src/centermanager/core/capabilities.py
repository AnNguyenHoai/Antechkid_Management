# -*- coding: utf-8 -*-
"""Canonical application authorization capabilities.

This module is the single vocabulary for capability identifiers. Persistence
models and legacy permission APIs may reference these values, but must not
create a second authorization vocabulary.
"""
from enum import Enum


class Capability(str, Enum):
    """Stable capability identifiers used by authorization decisions."""

    # Student
    STUDENT_READ = "student.read"
    STUDENT_VIEW = "student.view"
    STUDENT_CREATE = "student.create"
    STUDENT_UPDATE = "student.update"
    STUDENT_DELETE = "student.delete"
    STUDENT_ARCHIVE = "student.archive"
    STUDENT_EXPORT = "student.export"
    STUDENT_IMPORT = "student.import"

    # Teacher / class
    TEACHER_VIEW = "teacher.view"
    TEACHER_CREATE = "teacher.create"
    TEACHER_UPDATE = "teacher.update"
    TEACHER_DELETE = "teacher.delete"
    CLASS_VIEW = "class.view"
    CLASS_CREATE = "class.create"
    CLASS_UPDATE = "class.update"
    CLASS_DELETE = "class.delete"
    CLASS_TEACHER_ASSIGNMENT_MANAGE = "class.teacher_assignment.manage"

    # Finance / reports / settings
    FINANCE_VIEW = "finance.view"
    FINANCE_INCOME_CREATE = "finance.income.create"
    FINANCE_INCOME_UPDATE = "finance.income.update"
    FINANCE_INCOME_DELETE = "finance.income.delete"
    FINANCE_EXPENSE_CREATE = "finance.expense.create"
    FINANCE_EXPENSE_UPDATE = "finance.expense.update"
    FINANCE_EXPENSE_DELETE = "finance.expense.delete"
    REPORT_VIEW = "report.view"
    SETTING_UPDATE = "setting.update"

    # Attendance / lessons
    ATTENDANCE_VIEW = "attendance.view"
    ATTENDANCE_CREATE = "attendance.create"
    ATTENDANCE_UPDATE = "attendance.update"
    LESSON_VIEW = "lesson.view"
    LESSON_CREATE = "lesson.create"
    LESSON_UPDATE = "lesson.update"
    LESSON_CANCEL = "lesson.cancel"

    # User / role administration
    USER_MANAGE = "user.manage"
    USER_VIEW = "user.view"
    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"
    USER_RESET_PASSWORD = "user.reset_password"
    ROLE_VIEW = "role.view"
    ROLE_MANAGE = "role.manage"
    AUDIT_VIEW = "audit.view"
    SYSTEM_DIAGNOSTICS_VIEW = "system.diagnostics.view"
    BACKUP_VIEW = "backup.view"
    BACKUP_CREATE = "backup.create"
    BACKUP_RESTORE = "backup.restore"

    # Employee
    EMPLOYEE_VIEW = "employee.view"
    EMPLOYEE_VIEW_SELF = "employee.view.self"
    EMPLOYEE_VIEW_ALL = "employee.view.all"
    EMPLOYEE_UPDATE_SELF = "employee.update.self"
    EMPLOYEE_CREATE = "employee.create"
    EMPLOYEE_UPDATE = "employee.update"
    EMPLOYEE_DELETE = "employee.delete"
    EMPLOYEE_ARCHIVE = "employee.archive"

    # Employee schedule / working time
    SCHEDULE_VIEW_SELF = "schedule.view.self"
    SCHEDULE_VIEW_ALL = "schedule.view.all"
    SCHEDULE_MANAGE = "schedule.manage"
    WORKING_TIME_VIEW_SELF = "working_time.view.self"
    WORKING_TIME_VIEW_ALL = "working_time.view.all"
    WORKING_TIME_CREATE_SELF = "working_time.create.self"
    WORKING_TIME_MANAGE = "working_time.manage"
    WORKING_TIME_LOCK = "working_time.lock"

    # Monthly work registration
    WORK_REGISTRATION_SELF = "work_registration.self"
    WORK_REGISTRATION_VIEW_ALL = "work_registration.view.all"
    WORK_REGISTRATION_MANAGE = "work_registration.manage"
    WORK_REGISTRATION_PERIOD_ADMIN_OVERRIDE = "work_registration.period.admin_override"
    WORK_REGISTRATION_DELETE = "work_registration.delete"

    @classmethod
    def values(cls) -> tuple[str, ...]:
        """Return the canonical capability identifiers."""
        return tuple(capability.value for capability in cls)

    @classmethod
    def from_value(cls, value: str) -> "Capability":
        """Resolve a persisted capability identifier or fail explicitly."""
        try:
            return cls(value)
        except ValueError as exc:
            raise ValueError(f"Unknown capability: {value}") from exc

    @classmethod
    def category(cls, value: str) -> str:
        """Return the stable permission category used by the persistence UI."""
        if value.startswith("student."):
            return "student"
        if value.startswith("teacher."):
            return "teacher"
        if value.startswith("class."):
            return "class"
        if value.startswith("finance."):
            return "finance"
        if value.startswith("report."):
            return "report"
        if value.startswith("setting."):
            return "setting"
        if value.startswith("attendance."):
            return "attendance"
        if value.startswith("lesson."):
            return "lesson"
        if value.startswith(("user.", "role.", "audit.", "system.", "backup.")):
            return "admin"
        if value.startswith(("employee.", "schedule.", "working_time.", "work_registration.")):
            return "employee"
        return "other"


# Explicit policy exceptions. New capabilities are not automatically granted
# to Manager merely because they were added to the canonical registry.
ADMIN_ONLY_CAPABILITIES = frozenset({
    Capability.WORK_REGISTRATION_PERIOD_ADMIN_OVERRIDE.value,
    Capability.WORK_REGISTRATION_DELETE.value,
    Capability.EMPLOYEE_DELETE.value,
})
