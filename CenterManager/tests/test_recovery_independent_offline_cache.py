"""Independent signed Git MAIN cache, never Recovery approval or audit state."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.platform.sync.offline_main_receipt import (
    record_authenticated_main,
    verify_authenticated_cache,
)


@pytest.fixture
def accepted_cache(monkeypatch, tmp_path):
    from centermanager.database import encryption

    root = tmp_path / "runtime"
    db_dir = root / "Database"
    repo_dir = root / "repository" / "database"
    db_dir.mkdir(parents=True)
    repo_dir.mkdir(parents=True)
    (db_dir / "center.db").write_bytes(b"synthetic-authenticated-runtime")
    (repo_dir / "center.db").write_bytes(b"synthetic-authenticated-main")
    secrets = {"key": b"synthetic-protected-key"}
    monkeypatch.setattr(encryption, "database_encryption_required", lambda: True)
    monkeypatch.setattr(
        encryption, "DatabaseKeyStore",
        lambda: SimpleNamespace(load=lambda: secrets["key"]),
    )
    paths = SimpleNamespace(runtime_root=root, database_dir=db_dir)
    provider = SimpleNamespace(
        get_local_main_commit=lambda: "a" * 40,
        observe_remote_main_commit=lambda: "a" * 40,
    )
    return paths, provider, secrets


def test_online_acceptance_records_offline_proof_without_recovery(accepted_cache):
    paths, provider, _ = accepted_cache
    record_authenticated_main(provider, paths)
    assert verify_authenticated_cache(paths)


def test_old_recovery_cannot_influence_signed_offline_proof(
    monkeypatch, accepted_cache,
):
    paths, provider, _ = accepted_cache
    record_authenticated_main(provider, paths)
    from centermanager.platform import write_recovery

    monkeypatch.setattr(
        write_recovery, "WriteRecoveryJournal",
        lambda *_: (_ for _ in ()).throw(
            AssertionError("Offline READ must not inspect Recovery")
        ),
    )
    assert verify_authenticated_cache(paths)


def test_tampered_cache_or_database_is_rejected(accepted_cache):
    paths, provider, _ = accepted_cache
    record_authenticated_main(provider, paths)
    (paths.database_dir / "center.db").write_bytes(b"malicious-local-edit")
    assert not verify_authenticated_cache(paths)


def test_different_database_key_invalidates_cache(accepted_cache):
    paths, provider, secrets = accepted_cache
    record_authenticated_main(provider, paths)
    secrets["key"] = b"different-protected-key"
    assert not verify_authenticated_cache(paths)


def test_remote_oid_race_cannot_mint_offline_proof(accepted_cache):
    paths, provider, _ = accepted_cache
    provider.observe_remote_main_commit = lambda: "b" * 40
    with pytest.raises(ValueError, match="Exact authoritative"):
        record_authenticated_main(provider, paths)
    assert not verify_authenticated_cache(paths)


def test_cached_attestation_is_outside_recovery_and_git_runtime(accepted_cache):
    paths, provider, _ = accepted_cache
    record_authenticated_main(provider, paths)
    proof = paths.runtime_root.with_name(
        paths.runtime_root.name + ".accepted-main"
    ) / "read-cache.json"
    assert proof.is_file()
    assert "write-recovery" not in str(proof)
    assert not proof.is_relative_to(paths.runtime_root)
