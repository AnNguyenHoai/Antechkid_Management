# -*- coding: utf-8 -*-
"""
Business exceptions for Service layer.
"""


class StudentServiceError(Exception):
    """Base exception for StudentService."""
    pass


class StudentNotFoundError(StudentServiceError):
    """Raised when a Student is not found (active or including deleted)."""
    pass


class StudentValidationError(StudentServiceError):
    """Raised when validation fails."""
    pass


class StudentAlreadyDeletedError(StudentServiceError):
    """Raised when attempting to delete an already deleted Student."""
    pass


class StudentNotDeletedError(StudentServiceError):
    """Raised when attempting to restore a Student that is not deleted."""
    pass