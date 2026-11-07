"""REC-03: archived incidents cannot authenticate a stale active database."""
import json
import hashlib
from types import SimpleNamespace

import pytest

from centermanager.platform.sync.active_main_generation import (
    ActiveMainError, verify_active_main_generation,
)
from centermanager.platform.sync.main_stage import stage_exact_main


def test_generation_proof_does_not_depend_on_historic_recovery_case(tmp_path):
    repo = tmp_path / "repository"
    database_dir = repo / "database"
    database_dir.mkdir(parents=True)
    (database_dir / "center.db").write_bytes(b"MAIN-byte-contract")
    (database_dir / "center.db.identity.json").write_text('{"signed":"test"}')
    (repo / "manifest.json").write_text('{"runtime_version":1}')
    oid = "c" * 40
    provider = SimpleNamespace(
        get_fetched_remote_main_commit=lambda: oid,
        get_local_main_commit=lambda: oid,
        observe_remote_main_commit=lambda: oid,
    )
    stage = stage_exact_main(provider, repo, tmp_path / "stage", validate=lambda _: None)
    # A pending legacy case is separate from a freshly accepted MAIN generation.
    archived = tmp_path / "old-runtime.write-recovery"
    archived.mkdir()
    (archived / "journal.json").write_text('{"status":"OPEN"}')
    result = verify_active_main_generation(stage.path, expected_main_oid=oid)
    assert result.commit_oid == oid
    assert result.database_path.read_bytes() == b"MAIN-byte-contract"
    assert (archived / "journal.json").read_text() == '{"status":"OPEN"}'


@pytest.mark.parametrize("tamper", ["bytes", "oid", "receipt", "missing"])
def test_refuses_unverified_or_changed_active_main(tmp_path, tamper):
    candidate = tmp_path / "candidate"
    (candidate / "database").mkdir(parents=True)
    database = candidate / "database" / "center.db"
    database.write_bytes(b"original")
    oid = "a" * 40
    receipt = {
        "format": 1,
        "accepted_main_oid": oid,
        "center_db_sha256": hashlib.sha256(b"original").hexdigest(),
    }
    path = candidate / "accepted-main.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    if tamper == "bytes":
        database.write_bytes(b"corrupt")
    if tamper == "oid":
        receipt["accepted_main_oid"] = "b" * 40
        path.write_text(json.dumps(receipt), encoding="utf-8")
    if tamper == "receipt":
        path.write_text("{not json", encoding="utf-8")
    if tamper == "missing":
        path.unlink()
    with pytest.raises(ActiveMainError):
        verify_active_main_generation(candidate, expected_main_oid=oid)
