"""REC-05: failure injection must retain original local and Recovery bytes."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.platform.sync import main_stage
from centermanager.platform.sync.active_main_generation import (
    ActiveMainError, verify_active_main_generation,
)
from centermanager.platform.sync.main_stage import MainStageError, stage_exact_main


@pytest.fixture
def isolated_inputs(tmp_path):
    repo = tmp_path / "repository"
    dbdir = repo / "database"
    dbdir.mkdir(parents=True)
    (dbdir / "center.db").write_bytes(b"MAIN encrypted database")
    (dbdir / "center.db.identity.json").write_text("signed identity")
    (repo / "manifest.json").write_text('{"runtime_version": 4}')
    runtime_dir = tmp_path / "runtime" / "Database"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "center.db").write_bytes(b"UNPUBLISHED local")
    (runtime_dir / "center.db-wal").write_bytes(b"UNPUBLISHED wal")
    recovery = tmp_path / "runtime.write-recovery"
    recovery.mkdir()
    (recovery / "journal.json").write_bytes(b'{"status": "PUBLISHING"}')
    identity = "f" * 40
    remote = {"oid": identity}
    provider = SimpleNamespace(
        get_fetched_remote_main_commit=lambda: identity,
        get_local_main_commit=lambda: identity,
        observe_remote_main_commit=lambda: remote["oid"],
    )
    evidence = {
        "db": (runtime_dir / "center.db").read_bytes(),
        "wal": (runtime_dir / "center.db-wal").read_bytes(),
        "journal": (recovery / "journal.json").read_bytes(),
    }
    return repo, provider, remote, runtime_dir, recovery, evidence


def _assert_originals_untouched(fixture):
    _, _, _, runtime_dir, recovery, evidence = fixture
    assert (runtime_dir / "center.db").read_bytes() == evidence["db"]
    assert (runtime_dir / "center.db-wal").read_bytes() == evidence["wal"]
    assert (recovery / "journal.json").read_bytes() == evidence["journal"]


def test_remote_advance_during_staging_never_accepts_stage(isolated_inputs):
    repo, provider, remote, runtime, recovery, evidence = isolated_inputs
    def advance(_):
        remote["oid"] = "b" * 40
    with pytest.raises(MainStageError, match="advanced"):
        stage_exact_main(provider, repo, runtime.parent.parent / "candidates", validate=advance)
    assert list((runtime.parent.parent / "candidates").iterdir()) == []
    _assert_originals_untouched(isolated_inputs)


@pytest.mark.parametrize("failing_copy", [1, 2, 3])
def test_partial_copy_or_access_denied_preserves_local_and_drops_only_stage(
    isolated_inputs, monkeypatch, failing_copy
):
    repo, provider, remote, runtime, recovery, evidence = isolated_inputs
    original = main_stage._copy_durable
    call = {"n": 0}
    def interrupted(src, dest):
        call["n"] += 1
        if call["n"] == failing_copy:
            raise PermissionError("simulated locked file")
        return original(src, dest)
    monkeypatch.setattr(main_stage, "_copy_durable", interrupted)
    stage_root = runtime.parent.parent / "candidates"
    with pytest.raises(PermissionError, match="locked file"):
        stage_exact_main(provider, repo, stage_root, validate=lambda _: None)
    assert list(stage_root.iterdir()) == []
    _assert_originals_untouched(isolated_inputs)


def test_identity_validation_failure_does_not_advance_source_or_recovery(
    isolated_inputs, monkeypatch
):
    repo, provider, remote, runtime, recovery, evidence = isolated_inputs
    from centermanager.database import encryption, artifact_identity, artifact_security
    monkeypatch.setattr(encryption, "database_encryption_required", lambda: True)
    monkeypatch.setattr(encryption.DatabaseKeyStore, "load", lambda self: b"x" * 32)
    monkeypatch.setattr(artifact_security, "validate_database_artifact", lambda *a, **kw: None)
    def reject_identity(*_args):
        raise ValueError("signed identity does not match")
    monkeypatch.setattr(artifact_identity, "validate_identity", reject_identity)
    with pytest.raises(ValueError, match="signed identity"):
        stage_exact_main(provider, repo, runtime.parent.parent / "candidates")
    _assert_originals_untouched(isolated_inputs)


def test_complete_stage_cannot_be_construed_as_active_without_matching_receipt(
    isolated_inputs
):
    repo, provider, remote, runtime, recovery, evidence = isolated_inputs
    accepted = stage_exact_main(provider, repo, runtime.parent.parent / "candidates", validate=lambda _: None)
    assert verify_active_main_generation(accepted.path, expected_main_oid=accepted.commit_oid)
    proof = accepted.path / "accepted-main.json"
    content = json.loads(proof.read_text())
    content["center_db_sha256"] = "0" * 64
    proof.write_text(json.dumps(content))
    with pytest.raises(ActiveMainError, match="differs"):
        verify_active_main_generation(accepted.path, expected_main_oid=accepted.commit_oid)
    _assert_originals_untouched(isolated_inputs)
