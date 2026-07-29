# -*- coding: utf-8 -*-
"""
Permission definitions and placeholder authorization.
"""
from enum import Enum


class Permission(Enum):
    """Application-level permissions."""
    STUDENT_READ = "student.read"
    STUDENT_CREATE = "student.create"
    STUDENT_UPDATE = "student.update"
    STUDENT_ARCHIVE = "student.archive"
    STUDENT_EXPORT = "student.export"
    STUDENT_IMPORT = "student.import"


def has_permission(permission: Permission, user=None) -> bool:
    """
    Placeholder permission check.
    In future, this will check the current user's roles.
    For now, always return True.
    """
    # TODO: implement actual authorization
    return True