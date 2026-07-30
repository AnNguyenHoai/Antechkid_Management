# -*- coding: utf-8 -*-
"""
Permission definitions and authorization.
"""
from enum import Enum
from typing import Optional, List

from centermanager.core.current_user import get_current_user


class Permission(Enum):
    """Application-level permissions."""
    STUDENT_READ = "student.read"
    STUDENT_CREATE = "student.create"
    STUDENT_UPDATE = "student.update"
    STUDENT_ARCHIVE = "student.archive"
    STUDENT_EXPORT = "student.export"
    STUDENT_IMPORT = "student.import"
    
    # RBAC permissions (aligned with PermissionDefinitions)
    STUDENT_VIEW = "student.view"
    STUDENT_DELETE = "student.delete"
    TEACHER_VIEW = "teacher.view"
    TEACHER_CREATE = "teacher.create"
    TEACHER_UPDATE = "teacher.update"
    TEACHER_DELETE = "teacher.delete"
    FINANCE_VIEW = "finance.view"
    FINANCE_INCOME_CREATE = "finance.income.create"
    FINANCE_INCOME_UPDATE = "finance.income.update"
    FINANCE_INCOME_DELETE = "finance.income.delete"
    FINANCE_EXPENSE_CREATE = "finance.expense.create"
    FINANCE_EXPENSE_UPDATE = "finance.expense.update"
    FINANCE_EXPENSE_DELETE = "finance.expense.delete"
    REPORT_VIEW = "report.view"
    SETTING_UPDATE = "setting.update"


def has_permission(permission: Permission, user=None) -> bool:
    """
    Check if the current user has a permission.
    
    Args:
        permission: The Permission enum value to check.
        user: Optional user to check. If None, uses current user.
    
    Returns:
        True if the user has the permission, False otherwise.
    """
    from centermanager.services.permission_service import PermissionService
    from centermanager.database.engine import create_production_engine
    from sqlalchemy.orm import sessionmaker
    
    if user is None:
        user = get_current_user()
    if user is None:
        return False
    
    # Use PermissionService for real checking
    engine = create_production_engine()
    session_factory = sessionmaker(bind=engine)
    service = PermissionService(session_factory)
    return service.has_permission(permission.value, user)


def require_permission(permission: Permission, user=None) -> None:
    """
    Require a permission. Raises PermissionDeniedError if not granted.
    """
    if not has_permission(permission, user):
        from centermanager.services.permission_service import PermissionDeniedError
        raise PermissionDeniedError(f"Permission '{permission.value}' is required.")


# Legacy alias
def has_permission_legacy(permission: Permission, user=None) -> bool:
    """Legacy function for backward compatibility."""
    return has_permission(permission, user)