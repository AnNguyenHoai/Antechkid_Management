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
