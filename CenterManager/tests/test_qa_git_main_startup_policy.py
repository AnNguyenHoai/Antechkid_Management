"""Git MAIN wins startup policy, without losing safe fallback on failed proof.

Only disposable paths and fake Git observations; never production workspace.
"""
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.platform.sync.startup_sync import StartupSynchronization
from centermanager.platform.write_recovery import RecoveryRequired


def test_legacy_drift_requires_remote_proof_before_reconciliation(monkeypatch):
    events = []
    class Journal:
        def assert_replaceable(self, legacy=False):
            events.append(("check", legacy))
            if legacy:
                raise RecoveryRequired("legacy local drift")
        def inspect(self):
            return None
        def reconcile(self, **kwargs):
            events.append(("reconcile", kwargs["accepted_main"]))
    monkeypatch.setattr("centermanager.platform.write_recovery.WriteRecoveryJournal", Journal)
    remote = SimpleNamespace(
        get_fetched_remote_main_commit=lambda: "a" * 40,
        observe_remote_main_commit=lambda: "b" * 40,
        get_local_main_commit=lambda: "c" * 40,
    )
    startup = StartupSynchronization.__new__(StartupSynchronization)
    startup._provider = remote
    assert startup._prepare_authoritative_startup_replacement() is False
    assert not any(event[0] == "reconcile" for event in events)
    assert "cannot be independently verified" in startup.recovery_error


def test_legacy_drift_preserves_before_allowing_replace(monkeypatch):
    events = []
    class Journal:
        def assert_replaceable(self, legacy=False):
            events.append(("check", legacy))
            if legacy:
                raise RecoveryRequired("legacy local drift")
        def inspect(self):
            return None
        def reconcile(self, **kwargs):
            assert kwargs["base_oid"] == "b" * 40
            assert kwargs["observe_main"]() == "a" * 40
            events.append(("preserve-and-reconcile", kwargs["accepted_main"]))
    monkeypatch.setattr("centermanager.platform.write_recovery.WriteRecoveryJournal", Journal)
    remote = SimpleNamespace(
        get_fetched_remote_main_commit=lambda: "a" * 40,
        observe_remote_main_commit=lambda: "a" * 40,
        get_local_main_commit=lambda: "b" * 40,
    )
    startup = StartupSynchronization.__new__(StartupSynchronization)
    startup._provider = remote
    assert startup._prepare_authoritative_startup_replacement() is True
    assert events == [
        ("check", True),
        ("preserve-and-reconcile", "a" * 40),
        ("check", False),
    ]


def test_atomic_install_discards_stale_wal_only_after_validated_stage(tmp_path, monkeypatch):
    source = tmp_path / "repository" / "database" / "center.db"
    source.parent.mkdir(parents=True)
    local = tmp_path / "Database" / "center.db"
    local.parent.mkdir()
    for path, value in ((source, "MAIN"), (local, "OLD_LOCAL")):
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE t(v TEXT)")
            db.execute("INSERT INTO t VALUES (?)", (value,))
    wal = local.with_name("center.db-wal")
    wal.write_bytes(b"stale wal from old generation")
    from centermanager.database import session
    from centermanager.database import encryption
    from centermanager.database import artifact_security
    monkeypatch.setattr(session, "quiesce_runtime_db", lambda: None)
    monkeypatch.setattr(encryption, "database_encryption_required", lambda: False)
    monkeypatch.setattr(artifact_security, "validate_database_artifact", lambda *a, **k: None)
    startup = StartupSynchronization.__new__(StartupSynchronization)
    startup._runtime_db_path = local
    assert startup._install_authoritative_database_atomically(source)
    assert not wal.exists()
    with sqlite3.connect(local) as db:
        assert db.execute("SELECT v FROM t").fetchone()[0] == "MAIN"
    assert local.read_bytes() == source.read_bytes()


def test_reset_pins_preflight_oid_and_refuses_remote_drift():
    seen = []
    class Provider:
        def _run_git_command(self, args):
            seen.append(tuple(args))
        def get_local_main_commit(self):
            return "a" * 40
        def observe_remote_main_commit(self):
            return "b" * 40  # Remote advanced after our preflight.
    startup = StartupSynchronization.__new__(StartupSynchronization)
    startup._provider = Provider()
    startup._accepted_startup_main_oid = "a" * 40
    assert startup._reset_to_remote() is False
    assert seen == [("reset", "--hard", "a" * 40)]


def test_reset_rejects_missing_accepted_oid_before_running_git():
    class Provider:
        def _run_git_command(self, args):
            raise AssertionError("unverified reset should never run")
    startup = StartupSynchronization.__new__(StartupSynchronization)
    startup._provider = Provider()
    assert startup._reset_to_remote() is False


def test_post_install_failure_restores_previous_db_and_sidecar(tmp_path, monkeypatch):
    source = tmp_path / "repo" / "center.db"
    source.parent.mkdir()
    old = tmp_path / "Database" / "center.db"
    old.parent.mkdir()
    for path, text in ((source, "REMOTE"), (old, "LOCAL")):
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE t(v TEXT)")
            db.execute("INSERT INTO t VALUES (?)", (text,))
    sidecar = old.with_name("center.db-wal")
    sidecar.write_bytes(b"synthetic legacy sidecar")
    from centermanager.database import session, encryption, artifact_security
    monkeypatch.setattr(session, "quiesce_runtime_db", lambda: None)
    monkeypatch.setattr(session, "refresh_runtime_db", lambda: None)
    monkeypatch.setattr(session, "runtime_db_maintenance_active", lambda: True)
    monkeypatch.setattr(encryption, "database_encryption_required", lambda: False)
    monkeypatch.setattr(artifact_security, "validate_database_artifact", lambda *a, **k: None)
    startup = StartupSynchronization.__new__(StartupSynchronization)
    startup._runtime_db_path = old
    original = old.read_bytes()
    assert startup._install_authoritative_database_atomically(source)
    startup._rollback_startup_database_install()
    assert old.read_bytes() == original
    assert sidecar.read_bytes() == b"synthetic legacy sidecar"
    assert getattr(startup, "_startup_db_install_backup", None) is None



def test_failed_install_rolls_back_local_git_head():
    calls = []
    old_sha = "1" * 40
    new_sha = "2" * 40
    class Provider:
        def _run_git_command(self, args):
            calls.append(args)
        def get_local_main_commit(self):
            return old_sha
    startup = StartupSynchronization.__new__(StartupSynchronization)
    startup._provider = Provider()
    startup._startup_previous_local_oid = old_sha
    startup._accepted_startup_main_oid = new_sha
    startup._rollback_startup_git_repository()
    assert calls == [["reset", "--hard", old_sha]]
    assert startup._startup_previous_local_oid is None
