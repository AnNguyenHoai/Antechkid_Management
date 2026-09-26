# -*- coding: utf-8 -*-
from pathlib import Path
from types import SimpleNamespace

import pytest

import centermanager.services.admin_data_reset_service as reset_module
from centermanager.repositories.admin_data_reset_repository import (
    AdminDataResetRepository,
    ResetPreviewData,
)
from centermanager.services.admin_data_reset_service import (
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
    def __init__(self, *, fail_commit=False):
        self.sessions = []
        self.fail_commit = fail_commit

    def __call__(self):
        session = FakeSession(fail_commit=self.fail_commit)
        self.sessions.append(session)
        return session


class FakeResetRepository:
    def __init__(self, preview):
        self.preview_data = preview
        self.deleted = False

    def preview(self, scope, *, include_finance=False):
        return self.preview_data

    def delete_tables(self, table_names):
        self.deleted = True
        return {name: self.preview_data.counts.get(name, 0) for name in table_names}


class FakeProvider:
    def __init__(self, repository):
        self.repository = repository

    def admin_data_resets(self, session):
        return self.repository


class FakeBackup:
    def __init__(self, success=True):
        self.success = success
        self.calls = []

    def create_backup(self, label):
        self.calls.append(label)
        return SimpleNamespace(
            success=self.success,
            backup_path=Path("backup/pre_reset") if self.success else None,
            error=None if self.success else "disk full",
        )


class FakeAudit:
    def __init__(self):
        self.calls = []

    def record_in_session(self, session, *args, **kwargs):
        self.calls.append((session, args, kwargs))


class FakeCollaboration:
    def __init__(self, writing=True):
        self.writing = writing

    def is_initialized(self):
        return True

    def is_writing(self):
        return self.writing


def _preview(*, blockers=None):
    return ResetPreviewData(
        tables=("students",),
        counts={"students": 3},
        blockers=blockers or {},
        finance_counts={"incomes": 2},
    )


def _service(monkeypatch, *, writing=True, preview=None, backup_success=True, fail_commit=False):
    monkeypatch.setattr(
        reset_module,
        "get_current_user",
        lambda: SimpleNamespace(id=1, username="admin", is_admin=True),
    )
    repository = FakeResetRepository(preview or _preview())
    provider = FakeProvider(repository)
    backup = FakeBackup(backup_success)
    audit = FakeAudit()
    sessions = SessionFactory(fail_commit=fail_commit)
    service = AdminDataResetService(
        sessions,
        collaboration_manager=FakeCollaboration(writing),
        backup_service=backup,
        audit_service=audit,
        repository_provider=provider,
    )
    return service, repository, backup, audit, sessions


def test_protected_identity_and_audit_tables_can_never_be_business_reset_targets():
    assert {"users", "roles", "permissions", "role_permissions", "audit_logs"} <= set(
        AdminDataResetRepository.PROTECTED_TABLES
    )


def test_non_admin_cannot_preview(monkeypatch):
    monkeypatch.setattr(
        reset_module,
        "get_current_user",
        lambda: SimpleNamespace(id=2, username="teacher", is_admin=False),
    )
    service = AdminDataResetService(
        SessionFactory(),
        collaboration_manager=FakeCollaboration(True),
        backup_service=FakeBackup(),
        audit_service=FakeAudit(),
        repository_provider=FakeProvider(FakeResetRepository(_preview())),
    )
    with pytest.raises(AdminDataResetAuthorizationError):
        service.preview("student")


def test_admin_without_write_mode_cannot_reset(monkeypatch):
    service, repository, backup, _audit, _sessions = _service(
        monkeypatch, writing=False
    )
    with pytest.raises(AdminDataResetAuthorizationError, match="WRITE mode"):
        service.reset(
            "student",
            reason="test",
            confirmation="RESET STUDENT",
        )
    assert not repository.deleted
    assert backup.calls == []


def test_typed_confirmation_is_required_before_backup(monkeypatch):
    service, repository, backup, _audit, _sessions = _service(monkeypatch)
    with pytest.raises(AdminDataResetValidationError, match="RESET STUDENT"):
        service.reset("student", reason="test", confirmation="yes")
    assert not repository.deleted
    assert backup.calls == []


def test_dependency_blocker_aborts_before_safety_backup(monkeypatch):
    service, repository, backup, _audit, _sessions = _service(
        monkeypatch, preview=_preview(blockers={"incomes": 2})
    )
    with pytest.raises(AdminDataResetValidationError, match="incomes=2"):
        service.reset(
            "student",
            reason="test",
            confirmation="RESET STUDENT",
        )
    assert not repository.deleted
    assert backup.calls == []


def test_backup_failure_aborts_without_deleting_rows(monkeypatch):
    service, repository, backup, _audit, _sessions = _service(
        monkeypatch, backup_success=False
    )
    with pytest.raises(AdminDataResetError, match="Safety backup failed"):
        service.reset(
            "student",
            reason="test",
            confirmation="RESET STUDENT",
        )
    assert not repository.deleted
    assert backup.calls == ["pre_data_reset_student"]


def test_successful_reset_deletes_after_backup_and_writes_audit(monkeypatch):
    service, repository, backup, audit, sessions = _service(monkeypatch)
    result = service.reset(
        "student",
        reason="Reset before regression test",
        confirmation="RESET STUDENT",
    )

    assert backup.calls == ["pre_data_reset_student"]
    assert repository.deleted
    assert result.deleted_rows == 3
    assert result.backup_path.endswith("pre_reset")
    assert audit.calls
    _session, args, kwargs = audit.calls[0]
    assert args[0] == "ADMIN_DATA_RESET"
    assert kwargs["details"]["scope"] == "student"
    assert kwargs["details"]["reason"] == "Reset before regression test"
    assert sum(session.commits for session in sessions.sessions) == 1


def test_commit_failure_propagates_and_never_reports_success(monkeypatch):
    service, repository, backup, audit, _sessions = _service(
        monkeypatch, fail_commit=True
    )
    with pytest.raises(RuntimeError, match="commit failed"):
        service.reset(
            "student",
            reason="test",
            confirmation="RESET STUDENT",
        )
    assert backup.calls
    assert repository.deleted
    assert audit.calls
