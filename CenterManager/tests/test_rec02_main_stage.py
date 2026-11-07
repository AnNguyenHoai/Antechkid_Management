"""REC-02 independent MAIN staging does not affect Recovery artifacts."""
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.platform.sync.main_stage import MainStageError, stage_exact_main


def _fixture(tmp_path, *, remote=None):
    repo = tmp_path / "repository"
    dbdir = repo / "database"
    dbdir.mkdir(parents=True)
    (dbdir / "center.db").write_bytes(b"authoritative-ciphertext")
    (dbdir / "center.db.identity.json").write_text('{"signed":"fixture"}')
    (repo / "manifest.json").write_text('{"runtime_version":1}')
    oid = "a" * 40
    provider = SimpleNamespace(
        get_fetched_remote_main_commit=lambda: oid,
        get_local_main_commit=lambda: oid,
        observe_remote_main_commit=lambda: remote if remote is not None else oid,
    )
    # Deliberate local user work and history: staging must never touch these.
    active = tmp_path / "runtime" / "Database"
    active.mkdir(parents=True)
    (active / "center.db").write_bytes(b"unpublished-local")
    (active / "center.db-wal").write_bytes(b"unpublished-wal")
    recovery = tmp_path / "runtime.write-recovery"
    recovery.mkdir()
    (recovery / "journal.json").write_text('{"status":"OPEN"}')
    return repo, provider, active, recovery


def test_stage_exact_accepted_main_without_mutating_live_local(tmp_path):
    repo, provider, active, recovery = _fixture(tmp_path)
    stage = stage_exact_main(provider, repo, tmp_path / "stages", validate=lambda _: None)
    assert stage.commit_oid == "a" * 40
    assert stage.sha256 == hashlib.sha256(b"authoritative-ciphertext").hexdigest()
    assert (stage.path / "accepted-main.json").is_file()
    assert (stage.path / "database" / "center.db").read_bytes() == b"authoritative-ciphertext"
    assert (active / "center.db").read_bytes() == b"unpublished-local"
    assert (active / "center.db-wal").read_bytes() == b"unpublished-wal"
    assert (recovery / "journal.json").read_text() == '{"status":"OPEN"}'


def test_refuse_to_stage_when_remote_moved(tmp_path):
    repo, provider, active, recovery = _fixture(tmp_path, remote="b" * 40)
    with pytest.raises(MainStageError, match="OID proof"):
        stage_exact_main(provider, repo, tmp_path / "stages", validate=lambda _: None)
    assert (active / "center.db").read_bytes() == b"unpublished-local"


def test_validation_failure_destroys_only_private_stage(tmp_path):
    repo, provider, active, recovery = _fixture(tmp_path)
    def invalid(_):
        raise MainStageError("invalid SQLCipher")
    with pytest.raises(MainStageError, match="invalid SQLCipher"):
        stage_exact_main(provider, repo, tmp_path / "stages", validate=invalid)
    assert not list((tmp_path / "stages").iterdir())
    assert (active / "center.db").read_bytes() == b"unpublished-local"
    assert (recovery / "journal.json").is_file()


def test_missing_identity_cannot_produce_accepted_stage(tmp_path):
    repo, provider, active, recovery = _fixture(tmp_path)
    (repo / "database" / "center.db.identity.json").unlink()
    with pytest.raises(MainStageError, match="Signed MAIN"):
        stage_exact_main(provider, repo, tmp_path / "stages", validate=lambda _: None)
    assert (active / "center.db").read_bytes() == b"unpublished-local"
