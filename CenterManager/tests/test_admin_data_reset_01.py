# -*- coding: utf-8 -*-
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

import centermanager.services.admin_data_reset as reset_module
from centermanager.database.base import Base
from centermanager.platform.backup.backup_service import BackupService
from centermanager.repositories.admin_data_reset_repository import (
    AdminDataResetRepository,
    ResetPreviewData,
)
from centermanager.services.admin_data_reset import (
    AdminDataResetAuthorizationError,
    AdminDataResetError,
    AdminDataResetService,
    AdminDataResetValidationError,
)


class FakeSession:
    def __init__(self, fail_commit=False):
        self.commits = 0
        self.fail_commit = fail_commit

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def commit(self):
        if self.fail_commit:
            raise RuntimeError("commit failed")
        self.commits += 1


class SessionFactory:
    def __init__(self, fail_commit=False):
        self.fail_commit = fail_commit
        self.sessions = []

    def __call__(self):
        session = FakeSession(self.fail_commit)
        self.sessions.append(session)
        return session


class FakeRepo:
    def __init__(self, preview):
        self.preview_data = preview
        self.cleared = False

    def preview(self, scope, *, include_finance=False):
        return self.preview_data

    def delete_tables(self, table_names):
        self.cleared = True
        return {name: self.preview_data.counts.get(name, 0) for name in table_names}


class FakeProvider:
    def __init__(self, repo):
        self.repo = repo

    def admin_data_resets(self, session):
        return self.repo


class FakeBackup:
    def __init__(self, success=True):
        self.success = success
        self.calls = []

    def create_backup(self, label):
        self.calls.append(label)
        return SimpleNamespace(
            success=self.success,
            backup_path=Path("backup/pre_reset") if self.success else None,
            error=None if self.success else "backup failed",
        )


class FakeAudit:
    def __init__(self):
        self.calls = []

    def record_in_session(self, session, *args, **kwargs):
        self.calls.append((session, args, kwargs))


class FakeCollaboration:
    def __init__(self, writing=True):
        self.writing = writing
        self.write_checks = 0

    def is_initialized(self):
        return True

    def is_writing(self):
        self.write_checks += 1
        if isinstance(self.writing, (list, tuple)):
            index = min(self.write_checks - 1, len(self.writing) - 1)
            return self.writing[index]
        return self.writing


def preview(blockers=None):
    return ResetPreviewData(
        tables=("students",),
        counts={"students": 3},
        blockers=blockers or {},
        finance_counts={"incomes": 2},
    )


def make_service(monkeypatch, *, writing=True, blockers=None, backup_success=True, fail_commit=False):
    monkeypatch.setattr(
        reset_module,
        "get_current_user",
        lambda: SimpleNamespace(id=1, username="admin", is_admin=True),
    )
    repo = FakeRepo(preview(blockers))
    backup = FakeBackup(backup_success)
    audit = FakeAudit()
    sessions = SessionFactory(fail_commit)
    service = AdminDataResetService(
        sessions,
        collaboration_manager=FakeCollaboration(writing),
        backup_service=backup,
        audit_service=audit,
        repository_provider=FakeProvider(repo),
    )
    return service, repo, backup, audit, sessions


def test_identity_and_audit_tables_are_protected():
    assert {"users", "roles", "permissions", "role_permissions", "audit_logs"} <= set(
        AdminDataResetRepository.PROTECTED_TABLES
    )


def test_every_current_mapped_table_is_explicitly_classified():
    mapped = set(Base.metadata.tables)
    classified = (
        set(AdminDataResetRepository.PROTECTED_TABLES)
        | set(AdminDataResetRepository.BUSINESS_TABLES)
    )
    assert mapped == classified


def test_employee_scope_covers_schedule_and_registration_children():
    employee_tables = set(AdminDataResetRepository.SCOPE_TABLES["employee"])
    assert {
        "employees",
        "employee_documents",
        "employee_schedule_rules",
        "employee_schedule_exceptions",
        "employee_schedule_weeks",
        "employee_schedule_assignments",
        "employee_work_registration_periods",
        "employee_work_registrations",
        "employee_work_registration_blocks",
        "employee_working_time_entries",
    } <= employee_tables
    assert "employee_schedules" not in employee_tables
    assert "employee_working_times" not in employee_tables


def test_all_business_fails_closed_for_unclassified_mapped_table(monkeypatch):
    repository = AdminDataResetRepository(SimpleNamespace())
    known = {name: object() for name in AdminDataResetRepository.BUSINESS_TABLES}
    known.update({name: object() for name in AdminDataResetRepository.PROTECTED_TABLES})
    known["future_system_config"] = object()
    monkeypatch.setattr(repository, "_all_tables", lambda: known)

    with pytest.raises(ValueError, match="future_system_config"):
        repository.resolve_tables("all_business")


def test_admin_write_mode_and_confirmation_are_required(monkeypatch):
    service, repo, backup, _audit, _sessions = make_service(monkeypatch, writing=False)
    with pytest.raises(AdminDataResetAuthorizationError, match="WRITE mode"):
        service.reset("student", reason="test", confirmation="RESET STUDENT")
    assert not repo.cleared and not backup.calls

    service, repo, backup, _audit, _sessions = make_service(monkeypatch)
    with pytest.raises(AdminDataResetValidationError, match="RESET STUDENT"):
        service.reset("student", reason="test", confirmation="yes")
    assert not repo.cleared and not backup.calls


def test_dependency_or_backup_failure_aborts_before_write(monkeypatch):
    service, repo, backup, _audit, _sessions = make_service(
        monkeypatch, blockers={"incomes": 2}
    )
    with pytest.raises(AdminDataResetValidationError, match="incomes=2"):
        service.reset("student", reason="test", confirmation="RESET STUDENT")
    assert not repo.cleared and not backup.calls

    service, repo, backup, _audit, _sessions = make_service(
        monkeypatch, backup_success=False
    )
    with pytest.raises(AdminDataResetError, match="Safety backup failed"):
        service.reset("student", reason="test", confirmation="RESET STUDENT")
    assert not repo.cleared


def test_write_ownership_is_revalidated_after_backup(monkeypatch):
    service, repo, backup, _audit, _sessions = make_service(
        monkeypatch, writing=[True, False]
    )
    with pytest.raises(AdminDataResetAuthorizationError, match="WRITE mode"):
        service.reset("student", reason="test", confirmation="RESET STUDENT")
    assert backup.calls == ["pre_data_reset_student"]
    assert not repo.cleared


def test_successful_reset_creates_backup_commits_and_audits(monkeypatch):
    service, repo, backup, audit, sessions = make_service(monkeypatch)
    result = service.reset(
        "student",
        reason="Reset before regression test",
        confirmation="RESET STUDENT",
    )
    assert backup.calls == ["pre_data_reset_student"]
    assert repo.cleared
    assert result.deleted_rows == 3
    assert audit.calls
    assert audit.calls[0][2]["details"]["reason"] == "Reset before regression test"
    assert sum(item.commits for item in sessions.sessions) == 1


def test_commit_failure_propagates(monkeypatch):
    service, repo, backup, audit, _sessions = make_service(monkeypatch, fail_commit=True)
    with pytest.raises(RuntimeError, match="commit failed"):
        service.reset("student", reason="test", confirmation="RESET STUDENT")
    assert backup.calls and repo.cleared and audit.calls


def test_sqlite_safety_snapshot_includes_committed_wal_rows(tmp_path):
    source_path = tmp_path / "source.db"
    snapshot_path = tmp_path / "snapshot.db"
    source = sqlite3.connect(source_path)
    try:
        assert source.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() == "wal"
        source.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        source.commit()
        source.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        source.execute("PRAGMA wal_autocheckpoint=0")
        source.execute("INSERT INTO sample(value) VALUES ('latest committed row')")
        source.commit()

        wal_path = Path(str(source_path) + "-wal")
        assert wal_path.is_file() and wal_path.stat().st_size > 0
        BackupService._copy_sqlite_snapshot(source_path, snapshot_path)
    finally:
        source.close()

    snapshot = sqlite3.connect(snapshot_path)
    try:
        rows = snapshot.execute("SELECT value FROM sample ORDER BY id").fetchall()
    finally:
        snapshot.close()
    assert rows == [("latest committed row",)]
