# -*- coding: utf-8 -*-
import os
import subprocess
import sys
from pathlib import Path

from git import Repo

from scripts.audit_authoritative_db_history import SQLITE_HEADER, audit_repository


def _commit(repo: Repo, path: Path, data: bytes, message: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    repo.index.add([str(path.relative_to(repo.working_tree_dir))])
    commit = repo.index.commit(message)
    return commit.hexsha


def _repo(tmp_path: Path) -> tuple[Repo, Path]:
    root = tmp_path / "data-repo"
    repo = Repo.init(root)
    with repo.config_writer() as cfg:
        cfg.set_value("user", "name", "Test")
        cfg.set_value("user", "email", "test@example.invalid")
    db = root / "database" / "center.db"
    return repo, db


def test_audit_flags_plaintext_current_and_history(tmp_path):
    repo, db = _repo(tmp_path)
    plain_sha = _commit(repo, db, SQLITE_HEADER + b"payload", "plain")

    result = audit_repository(Path(repo.working_tree_dir))

    assert result.current_plaintext is True
    assert result.reachable_plaintext_versions == 1
    assert result.plaintext_commits == [plain_sha]
    assert result.safe_for_in_place_append_only_cutover is False


def test_encrypting_head_does_not_make_plaintext_history_safe(tmp_path):
    repo, db = _repo(tmp_path)
    plain_sha = _commit(repo, db, SQLITE_HEADER + b"payload", "plain")
    _commit(repo, db, b"SQLCIPHER-CIPHERTEXT-NOT-SQLITE", "encrypted head")

    result = audit_repository(Path(repo.working_tree_dir))

    assert result.current_plaintext is False
    assert result.reachable_plaintext_versions == 1
    assert plain_sha in result.plaintext_commits
    assert result.safe_for_in_place_append_only_cutover is False
    assert "do not merely encrypt" in result.recommendation


def test_encrypted_only_history_is_append_only_safe(tmp_path):
    repo, db = _repo(tmp_path)
    _commit(repo, db, b"CIPHERTEXT-V1", "encrypted")
    _commit(repo, db, b"CIPHERTEXT-V2", "encrypted update")

    result = audit_repository(Path(repo.working_tree_dir))

    assert result.current_plaintext is False
    assert result.reachable_plaintext_versions == 0
    assert result.safe_for_in_place_append_only_cutover is True


def test_direct_cli_execution_bootstraps_application_src(tmp_path):
    repo, db = _repo(tmp_path)
    _commit(repo, db, b"CIPHERTEXT-V1", "encrypted")

    script = Path(__file__).resolve().parents[1] / "scripts" / "audit_authoritative_db_history.py"
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    completed = subprocess.run(
        [sys.executable, str(script), "--repo", str(repo.working_tree_dir)],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "ModuleNotFoundError" not in completed.stderr
    assert "Reachable plaintext versions: 0" in completed.stdout
