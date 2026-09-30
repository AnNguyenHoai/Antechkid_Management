# -*- coding: utf-8 -*-
"""Regression coverage for SEC06 Windows lock-owner diagnostics."""
from pathlib import Path

import pytest

from centermanager.database import session as session_module
from centermanager.platform.backup.windows_lock_diagnostics import (
    FileLockOwner,
    format_lock_owners,
)


def test_format_lock_owners_includes_pid_app_and_service():
    text = format_lock_owners(
        [FileLockOwner(pid=4321, application_name="CenterManager.exe", service_short_name="svc")]
    )
    assert "pid=4321" in text
    assert "CenterManager.exe" in text
    assert "service=svc" in text


def test_quiesce_fails_before_swap_when_windows_reports_lock_owner(monkeypatch):
    calls = []
    monkeypatch.setattr(session_module, "begin_runtime_db_maintenance", lambda: calls.append("begin"))
    monkeypatch.setattr(session_module, "close_all_sessions", lambda: calls.append("sessions"))
    monkeypatch.setattr(session_module, "dispose_runtime_engines", lambda: calls.append("engines"))
    monkeypatch.setattr(session_module, "close_runtime_dbapi_connections", lambda: calls.append("dbapi"))
    monkeypatch.setattr(session_module, "runtime_dbapi_connection_count", lambda: 0)
    monkeypatch.setattr(session_module, "get_database_path", lambda: Path("C:/runtime/Database/center.db"))
    monkeypatch.setattr(
        session_module,
        "windows_lock_owners",
        lambda path: [FileLockOwner(pid=9876, application_name="external.exe")],
    )
    monkeypatch.setattr(session_module, "end_runtime_db_maintenance", lambda: calls.append("end"))

    with pytest.raises(RuntimeError) as exc_info:
        session_module.quiesce_runtime_db()

    message = str(exc_info.value)
    assert "still locked after quiesce" in message
    assert "pid=9876" in message
    assert "external.exe" in message
    assert calls == ["begin", "sessions", "engines", "dbapi", "end"]


def test_quiesce_continues_when_no_windows_owner_is_reported(monkeypatch):
    calls = []
    monkeypatch.setattr(session_module, "begin_runtime_db_maintenance", lambda: calls.append("begin"))
    monkeypatch.setattr(session_module, "close_all_sessions", lambda: calls.append("sessions"))
    monkeypatch.setattr(session_module, "dispose_runtime_engines", lambda: calls.append("engines"))
    monkeypatch.setattr(session_module, "close_runtime_dbapi_connections", lambda: calls.append("dbapi"))
    monkeypatch.setattr(session_module, "runtime_dbapi_connection_count", lambda: 0)
    monkeypatch.setattr(session_module, "get_database_path", lambda: Path("C:/runtime/Database/center.db"))
    monkeypatch.setattr(session_module, "windows_lock_owners", lambda path: [])

    session_module.quiesce_runtime_db()

    assert calls == ["begin", "sessions", "engines", "dbapi"]
