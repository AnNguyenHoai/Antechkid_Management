# -*- coding: utf-8 -*-
"""Database lifecycle state and validation contract."""
from __future__ import annotations

import sqlite3
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, Any


class DatabaseLifecycleState(str, Enum):
    """Operational state of the runtime database."""

    AVAILABLE = "available"
    MISSING = "missing"
    CORRUPTED = "corrupted"
    UNREADABLE = "unreadable"
    INVALID_SCHEMA = "invalid_schema"
    RECOVERY_REQUIRED = "recovery_required"

    @property
    def is_usable(self) -> bool:
        return self is DatabaseLifecycleState.AVAILABLE

    @property
    def requires_recovery(self) -> bool:
        return self is not DatabaseLifecycleState.AVAILABLE


class DatabaseLifecycleError(RuntimeError):
    """Raised when the application attempts to use an unavailable database."""


class DatabaseLifecycle:
    """Detect database health without creating or mutating the database file.

    ``readonly_connector`` lets encrypted production callers provide an already
    keyed SQLCipher connection while preserving the historical plain-SQLite
    behavior used by low-level tests and non-Windows development.
    """

    def __init__(
        self,
        database_path: Path,
        readonly_connector: Optional[Callable[[Path], Any]] = None,
    ) -> None:
        self._database_path = Path(database_path)
        self._readonly_connector = readonly_connector

    @property
    def database_path(self) -> Path:
        return self._database_path

    def _connect_readonly(self):
        if self._readonly_connector is not None:
            return self._readonly_connector(self._database_path)
        return sqlite3.connect(
            f"file:{self._database_path.resolve()}?mode=ro",
            uri=True,
        )

    def inspect(self) -> DatabaseLifecycleState:
        """Inspect the database file in read-only mode."""
        if not self._database_path.exists():
            return DatabaseLifecycleState.MISSING
        if not self._database_path.is_file():
            return DatabaseLifecycleState.UNREADABLE
        try:
            if self._database_path.stat().st_size == 0:
                return DatabaseLifecycleState.CORRUPTED
            connection = self._connect_readonly()
            try:
                integrity = connection.execute("PRAGMA integrity_check").fetchone()
                if not integrity or integrity[0] != "ok":
                    return DatabaseLifecycleState.CORRUPTED
                tables = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' LIMIT 1"
                ).fetchone()
                if tables is None:
                    return DatabaseLifecycleState.INVALID_SCHEMA
            finally:
                connection.close()
        except (sqlite3.DatabaseError, Exception) as exc:
            # SQLCipher DB-API exceptions are not subclasses of stdlib sqlite3
            # on every supported wheel, so classify DB-driver failures without
            # allowing them to escape the lifecycle boundary. Permission and OS
            # failures remain UNREADABLE below when recognizable.
            if isinstance(exc, (OSError, PermissionError)):
                return DatabaseLifecycleState.UNREADABLE
            return DatabaseLifecycleState.CORRUPTED
        return DatabaseLifecycleState.AVAILABLE

    def require_available(self) -> None:
        """Reject operational use unless the database is healthy."""
        state = self.inspect()
        if state is not DatabaseLifecycleState.AVAILABLE:
            raise DatabaseLifecycleError(
                f"Database lifecycle state is {state.value}; recovery is required."
            )

    def state_or_recovery(self) -> DatabaseLifecycleState:
        """Normalize every non-available state to the recovery-required contract."""
        state = self.inspect()
        return state if state is DatabaseLifecycleState.AVAILABLE else DatabaseLifecycleState.RECOVERY_REQUIRED
