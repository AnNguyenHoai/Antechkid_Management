# -*- coding: utf-8 -*-
"""Database lifecycle state and validation contract."""
from __future__ import annotations

import sqlite3
from enum import Enum
from pathlib import Path


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
    """Detect database health without creating or mutating the database file."""

    def __init__(self, database_path: Path):
        self._database_path = Path(database_path)

    @property
    def database_path(self) -> Path:
        return self._database_path

    def inspect(self) -> DatabaseLifecycleState:
        """Inspect the database file using SQLite read-only mode."""
        if not self._database_path.exists():
            return DatabaseLifecycleState.MISSING
        if not self._database_path.is_file():
            return DatabaseLifecycleState.UNREADABLE
        try:
            if self._database_path.stat().st_size == 0:
                return DatabaseLifecycleState.CORRUPTED
            connection = sqlite3.connect(
                f"file:{self._database_path.resolve()}?mode=ro",
                uri=True,
            )
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
        except sqlite3.DatabaseError:
            return DatabaseLifecycleState.CORRUPTED
        except (OSError, PermissionError):
            return DatabaseLifecycleState.UNREADABLE
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
