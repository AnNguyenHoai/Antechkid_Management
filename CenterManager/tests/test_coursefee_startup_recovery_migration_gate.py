"""Recovery advisory must not block authenticated Git MAIN schema startup.

Protect local WRITE and unknown data while allowing read-only schema checks
and a bounded in-process Alembic migration of exactly the accepted Git MAIN DB.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
import pytest

from centermanager.database import mutation_authority as authority


def test_migration_without_trusted_startup_proof_still_refuses_dirty_recovery(monkeypatch, tmp_path):
    from centermanager.platform import write_recovery
    db = tmp_path / "center.db"
    db.write_bytes(b"test-encrypted-main")
    monkeypatch.setattr(authority, "runtime_path", lambda: db)
    def refuse():
        raise write_recovery.RecoveryRequired("recovery pending")
    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", lambda: SimpleNamespace(assert_replaceable=refuse))
    with pytest.raises(write_recovery.RecoveryRequired, match="recovery pending"):
        with authority.system_mutation_permit("migration", path=db):
            pass


def test_scoped_migration_proof_allows_exact_main_but_never_other_work(monkeypatch, tmp_path):
    from centermanager.platform import write_recovery
    root = tmp_path / "runtime"
    db = root / "Database" / "center.db"
    repo = root / "repository"
    repo_db = repo / "database" / "center.db"
    db.parent.mkdir(parents=True)
    repo_db.parent.mkdir(parents=True)
    db.write_bytes(b"test-encrypted-main")
    repo_db.write_bytes(db.read_bytes())
    monkeypatch.setattr(authority, "runtime_path", lambda: db)
    document = SimpleNamespace(
        repository=repo, database=db, _wal_pending=lambda: False,
        assert_replaceable=lambda: (_ for _ in ()).throw(write_recovery.RecoveryRequired("pending")),
    )
    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", lambda: document)
    commit = "c" * 40
    provider = SimpleNamespace(
        _repo_path=repo,
        get_local_main_commit=lambda: commit,
        get_fetched_remote_main_commit=lambda: commit,
        observe_remote_main_commit=lambda: commit,
        _run_git_command=lambda args: "",
    )
    with authority.verified_authoritative_startup_migration(provider):
        with authority.system_mutation_permit("migration", path=db):
            assert authority._local.maintenance[3] == "migration"
        with pytest.raises(write_recovery.RecoveryRequired, match="pending"):
            with authority.system_mutation_permit("bootstrap", path=db):
                pass
    with pytest.raises(write_recovery.RecoveryRequired, match="pending"):
        with authority.system_mutation_permit("migration", path=db):
            pass
    assert getattr(authority._local, "startup_main_migration_path", None) is None


@pytest.mark.parametrize("problem", ["db_mismatch", "remote_mismatch", "repo_dirty", "wal", "editor"])
def test_scoped_migration_proof_rejects_unverified_main(monkeypatch, tmp_path, problem):
    from centermanager.platform import write_recovery
    db = tmp_path / "Database" / "center.db"
    repo = tmp_path / "repository"
    repo_db = repo / "database" / "center.db"
    db.parent.mkdir(parents=True)
    repo_db.parent.mkdir(parents=True)
    db.write_bytes(b"verified")
    repo_db.write_bytes(b"untrusted" if problem == "db_mismatch" else b"verified")
    monkeypatch.setattr(authority, "runtime_path", lambda: db)
    monkeypatch.setattr(
        write_recovery, "WriteRecoveryJournal",
        lambda: SimpleNamespace(repository=repo, database=db, _wal_pending=lambda: problem == "wal"),
    )
    commit = "d" * 40
    provider = SimpleNamespace(
        _repo_path=repo,
        get_local_main_commit=lambda: commit,
        get_fetched_remote_main_commit=lambda: commit,
        observe_remote_main_commit=lambda: "e" * 40 if problem == "remote_mismatch" else commit,
        _run_git_command=lambda args: "dirty" if problem == "repo_dirty" else "",
    )
    gate = authority.gate_for(db)
    if problem == "editor":
        gate.closed = False
    try:
        with pytest.raises(authority.MutationAuthorityError):
            with authority.verified_authoritative_startup_migration(provider):
                pass
    finally:
        gate.closed = True


def test_app_readonly_schema_first_and_optional_receipt_never_blocks():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "src/centermanager/app.py").read_text(encoding="utf-8")
    assert "verify_runtime_schema_readonly()" in src
    assert "verified_authoritative_startup_migration(sync_provider)" in src
    assert "schema_receipt_verified = False" in src
    assert "elif schema_receipt_verified:" in src
    assert "ensure_schema()" in src
    first = src.index("verify_runtime_schema_readonly()", src.index("def main("))
    scope = src.index("verified_authoritative_startup_migration(sync_provider)", first)
    assert first < scope
