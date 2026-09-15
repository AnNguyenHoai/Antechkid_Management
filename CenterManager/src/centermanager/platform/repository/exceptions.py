# -*- coding: utf-8 -*-
"""Repository exceptions."""


class RepositoryError(Exception):
    """Base exception for repository operations."""
    pass


class RepositoryNotFoundError(RepositoryError):
    """Repository directory does not exist."""
    pass


class ManifestNotFoundError(RepositoryError):
    """Runtime manifest not found."""
    pass


class ManifestInvalidError(RepositoryError):
    """Runtime manifest is invalid (missing fields, wrong schema)."""
    pass


class RuntimeCorruptedError(RepositoryError):
    """Runtime is corrupted (manifest exists but structure invalid)."""
    pass


class RuntimeValidationFailedError(RepositoryError):
    """Runtime validation failed (missing required folders, etc.)."""
    pass


class AtomicWriteError(RepositoryError):
    """Atomic write operation failed."""
    pass