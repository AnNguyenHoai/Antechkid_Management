# -*- coding: utf-8 -*-
from pathlib import Path
from types import SimpleNamespace

import pytest

import centermanager.services.admin_data_reset as reset_module
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

    def is_initialized(self):
        return True

    def is_writing(self):
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
