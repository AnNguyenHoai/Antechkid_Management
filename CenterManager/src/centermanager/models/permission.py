# -*- coding: utf-8 -*-
"""
Permission model - defines system permissions.
"""
from __future__ import annotations

from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from centermanager.models.role import Role


class Permission(Base, TimestampMixin):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Relationships
    roles: Mapped[List[Role]] = relationship(
        "Role",
        secondary="role_permissions",
        back_populates="permissions"
    )

    __table_args__ = (
        UniqueConstraint('name', name='uq_permission_name'),
    )

    def __repr__(self) -> str:
        return f"<Permission(id={self.id}, name='{self.name}')>"


# Permission definitions - canonical source
class PermissionDefinitions:
    """Central registry of all permissions in the system."""

    # Student
    STUDENT_VIEW = "student.view"
    STUDENT_CREATE = "student.create"
    STUDENT_UPDATE = "student.update"
    STUDENT_DELETE = "student.delete"

    # Teacher
    TEACHER_VIEW = "teacher.view"
    TEACHER_CREATE = "teacher.create"
    TEACHER_UPDATE = "teacher.update"
    TEACHER_DELETE = "teacher.delete"

    # Class
    CLASS_VIEW = "class.view"
    CLASS_CREATE = "class.create"
    CLASS_UPDATE = "class.update"
    CLASS_DELETE = "class.delete"

    # Finance
    FINANCE_VIEW = "finance.view"
    FINANCE_INCOME_CREATE = "finance.income.create"
    FINANCE_INCOME_UPDATE = "finance.income.update"
    FINANCE_INCOME_DELETE = "finance.income.delete"
    FINANCE_EXPENSE_CREATE = "finance.expense.create"
    FINANCE_EXPENSE_UPDATE = "finance.expense.update"
    FINANCE_EXPENSE_DELETE = "finance.expense.delete"

    # Reports
    REPORT_VIEW = "report.view"

    # Settings
    SETTING_UPDATE = "setting.update"

    ATTENDANCE_VIEW = "attendance.view"
    ATTENDANCE_CREATE = "attendance.create"
    ATTENDANCE_UPDATE = "attendance.update"

    LESSON_VIEW = "lesson.view"
    LESSON_CREATE = "lesson.create"
    LESSON_UPDATE = "lesson.update"
    LESSON_CANCEL = "lesson.cancel"
    USER_MANAGE = "user.manage"
    USER_VIEW = "user.view"
    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"
    USER_RESET_PASSWORD = "user.reset_password"

    # Role administration
    ROLE_VIEW = "role.view"
    ROLE_MANAGE = "role.manage"

    # Audit
    AUDIT_VIEW = "audit.view"
    @classmethod
    def all_permissions(cls) -> List[str]:
        return [
            cls.STUDENT_VIEW,
            cls.STUDENT_CREATE,
            cls.STUDENT_UPDATE,
            cls.STUDENT_DELETE,
            cls.TEACHER_VIEW,
            cls.TEACHER_CREATE,
            cls.TEACHER_UPDATE,
            cls.TEACHER_DELETE,
            cls.CLASS_VIEW,
            cls.CLASS_CREATE,
            cls.CLASS_UPDATE,
            cls.CLASS_DELETE,
            cls.FINANCE_VIEW,
            cls.FINANCE_INCOME_CREATE,
            cls.FINANCE_INCOME_UPDATE,
            cls.FINANCE_INCOME_DELETE,
            cls.FINANCE_EXPENSE_CREATE,
            cls.FINANCE_EXPENSE_UPDATE,
            cls.FINANCE_EXPENSE_DELETE,
            cls.REPORT_VIEW,
            cls.SETTING_UPDATE,
            cls.ATTENDANCE_VIEW,
            cls.ATTENDANCE_CREATE,
            cls.ATTENDANCE_UPDATE,
            cls.LESSON_VIEW,
            cls.LESSON_CREATE,
            cls.LESSON_UPDATE,
            cls.LESSON_CANCEL,
            cls.USER_MANAGE,
            cls.USER_VIEW,
            cls.USER_CREATE,
            cls.USER_UPDATE,
            cls.USER_DELETE,
            cls.USER_RESET_PASSWORD,
            cls.ROLE_VIEW,
            cls.ROLE_MANAGE,
            cls.AUDIT_VIEW,
        ]

    @classmethod
    def get_category(cls, permission_name: str) -> str:
        category_map = {
            cls.STUDENT_VIEW: "student",
            cls.STUDENT_CREATE: "student",
            cls.STUDENT_UPDATE: "student",
            cls.STUDENT_DELETE: "student",
            cls.TEACHER_VIEW: "teacher",
            cls.TEACHER_CREATE: "teacher",
            cls.TEACHER_UPDATE: "teacher",
            cls.TEACHER_DELETE: "teacher",
            cls.CLASS_VIEW: "class",
            cls.CLASS_CREATE: "class",
            cls.CLASS_UPDATE: "class",
            cls.CLASS_DELETE: "class",
            cls.FINANCE_VIEW: "finance",
            cls.FINANCE_INCOME_CREATE: "finance",
            cls.FINANCE_INCOME_UPDATE: "finance",
            cls.FINANCE_INCOME_DELETE: "finance",
            cls.FINANCE_EXPENSE_CREATE: "finance",
            cls.FINANCE_EXPENSE_UPDATE: "finance",
            cls.FINANCE_EXPENSE_DELETE: "finance",
            cls.REPORT_VIEW: "report",
            cls.SETTING_UPDATE: "setting",
            cls.ATTENDANCE_VIEW: "attendance",
            cls.ATTENDANCE_CREATE: "attendance",
            cls.ATTENDANCE_UPDATE: "attendance",
            cls.LESSON_VIEW: "lesson",
            cls.LESSON_CREATE: "lesson",
            cls.LESSON_UPDATE: "lesson",
            cls.LESSON_CANCEL: "lesson",
            cls.USER_MANAGE: "admin",
            cls.USER_VIEW: "admin",
            cls.USER_CREATE: "admin",
            cls.USER_UPDATE: "admin",
            cls.USER_DELETE: "admin",
            cls.USER_RESET_PASSWORD: "admin",
            cls.ROLE_VIEW: "admin",
            cls.ROLE_MANAGE: "admin",
            cls.AUDIT_VIEW: "admin",
        }

        return category_map.get(permission_name, "other")


# Alias for backward compatibility
PermissionName = PermissionDefinitions