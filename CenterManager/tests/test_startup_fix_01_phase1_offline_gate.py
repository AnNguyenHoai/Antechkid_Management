"""Offline READ derives authority from signed accepted-MAIN cache, never Recovery."""
from types import SimpleNamespace

import pytest

from centermanager.platform.sync.offline_read_gate import assess_offline_read
from centermanager.database.lifecycle import DatabaseLifecycleState


@pytest.fixture
def gate_fixture(monkeypatch, tmp_path):
    from centermanager.database import engine, artifact_security, encryption
    from centermanager.platform.sync import offline_main_receipt

    data = tmp_path / "Database"
    repo_db = tmp_path / "repository" / "database"
    data.mkdir()
    repo_db.mkdir(parents=True)
    runtime = data / "center.db"
    runtime.write_bytes(b"verified-runtime-db")
    (repo_db / "center.db").write_bytes(b"verified-Git-MAIN-db")

    cache = {"verified": True}
    monkeypatch.setattr(
        offline_main_receipt, "verify_authenticated_cache",
        lambda paths: cache["verified"],
    )
    monkeypatch.setattr(
        engine, "inspect_runtime_database",
        lambda: DatabaseLifecycleState.AVAILABLE,
    )
    monkeypatch.setattr(
        artifact_security, "validate_database_artifact",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(encryption, "database_encryption_required", lambda: False)
    return SimpleNamespace(
        paths=SimpleNamespace(database_dir=data, runtime_root=tmp_path),
        cache=cache, runtime=runtime,
    )


def test_verified_signed_cache_allows_offline_read_without_remote_fetch(gate_fixture):
    assert assess_offline_read(gate_fixture.paths).allowed


@pytest.mark.parametrize("historical_status", [
    "OPEN", "RECOVERY_REQUIRED", "CANCELLED", "RECONCILED", "CORRUPT",
])
def test_old_recovery_status_is_not_offline_read_gate(
    gate_fixture, monkeypatch, historical_status,
):
    # If Recovery inspection is attempted, fail the test. Git-main cache
    # authentication, not the user's pending review status, is the authority.
    from centermanager.platform import write_recovery

    monkeypatch.setattr(
        write_recovery, "WriteRecoveryJournal",
        lambda *_: (_ for _ in ()).throw(AssertionError(historical_status)),
    )
    assert assess_offline_read(gate_fixture.paths).allowed


def test_missing_signed_cache_cannot_be_treated_as_trusted_main(gate_fixture):
    gate_fixture.cache["verified"] = False
    assert not assess_offline_read(gate_fixture.paths).allowed


def test_uncheckpointed_wal_still_rejected(gate_fixture):
    gate_fixture.runtime.with_name("center.db-wal").write_bytes(b"pending")
    assert not assess_offline_read(gate_fixture.paths).allowed


def test_missing_cached_database_not_offline_first_install(gate_fixture):
    gate_fixture.runtime.unlink()
    assert not assess_offline_read(gate_fixture.paths).allowed


def test_corrupt_database_rejected_by_independent_integrity_verifier(
    gate_fixture, monkeypatch,
):
    from centermanager.database import artifact_security

    def corrupt(*args, **kwargs):
        raise RuntimeError("SQLCipher identity mismatch")

    monkeypatch.setattr(artifact_security, "validate_database_artifact", corrupt)
    assert not assess_offline_read(gate_fixture.paths).allowed
