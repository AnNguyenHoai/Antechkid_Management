"""STARTUP-FIX-01 P1: accepted local READ is validated without network/mutation."""
import hashlib
from types import SimpleNamespace

import pytest

from centermanager.platform.sync.offline_read_gate import assess_offline_read
from centermanager.database.lifecycle import DatabaseLifecycleState


@pytest.fixture
def gate_fixture(monkeypatch, tmp_path):
    from centermanager.database import engine, artifact_security, encryption
    from centermanager.platform import write_recovery

    data = tmp_path / "database"
    repo_db = tmp_path / "repository" / "database"
    data.mkdir()
    repo_db.mkdir(parents=True)
    runtime = data / "center.db"
    runtime.write_bytes(b"accepted-runtime")
    (repo_db / "center.db").write_bytes(b"accepted-main")
    receipt = {
        "status": "CLEAN", "publication": "VERIFIED",
        "published_runtime_sha256": hashlib.sha256(runtime.read_bytes()).hexdigest(),
    }
    journal = SimpleNamespace(
        inspect=lambda: receipt,
        assert_replaceable=lambda: None,
    )
    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", lambda _: journal)
    monkeypatch.setattr(engine, "inspect_runtime_database", lambda: DatabaseLifecycleState.AVAILABLE)
    monkeypatch.setattr(artifact_security, "validate_database_artifact", lambda *a, **kw: None)
    monkeypatch.setattr(encryption, "database_encryption_required", lambda: False)
    return SimpleNamespace(
        paths=SimpleNamespace(database_dir=data, runtime_root=tmp_path),
        journal=journal, receipt=receipt, runtime=runtime,
    )


def test_verified_clean_cached_runtime_can_be_read_without_remote_fetch(gate_fixture):
    assert assess_offline_read(gate_fixture.paths).allowed


@pytest.mark.parametrize("status,publication", [
    ("OPEN", "VERIFIED"),
    ("RECOVERY_REQUIRED", "VERIFIED"),
    ("RECONCILED", "VERIFIED"),
    ("CLEAN", "UNKNOWN"),
])
def test_pending_or_unaccepted_recovery_is_not_eligible(gate_fixture, status, publication):
    gate_fixture.receipt.update(status=status, publication=publication)
    assert not assess_offline_read(gate_fixture.paths).allowed


def test_runtime_change_after_clean_receipt_is_blocked(gate_fixture):
    gate_fixture.runtime.write_bytes(b"unaccepted-local-edit")
    assert not assess_offline_read(gate_fixture.paths).allowed


def test_unclean_wal_is_not_accepted(gate_fixture):
    gate_fixture.runtime.with_name("center.db-wal").write_bytes(b"pending")
    assert not assess_offline_read(gate_fixture.paths).allowed


def test_missing_cached_database_is_not_offline_first_install(gate_fixture):
    gate_fixture.runtime.unlink()
    assert not assess_offline_read(gate_fixture.paths).allowed


def test_failed_replaceability_proof_cannot_be_bypassed(gate_fixture):
    gate_fixture.journal.assert_replaceable = lambda: (_ for _ in ()).throw(
        RuntimeError("missing authoritative base")
    )
    assert not assess_offline_read(gate_fixture.paths).allowed


def test_corrupt_cached_database_rejected_by_integrity_verifier(gate_fixture, monkeypatch):
    from centermanager.database import artifact_security
    def corrupt(*args, **kwargs):
        raise RuntimeError("invalid SQLCipher")
    monkeypatch.setattr(artifact_security, "validate_database_artifact", corrupt)
    assert not assess_offline_read(gate_fixture.paths).allowed
