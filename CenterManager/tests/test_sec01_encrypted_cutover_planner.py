# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from git import Repo

import scripts.plan_sec01_encrypted_cutover as planner
from scripts.audit_authoritative_db_history import SQLITE_HEADER


def _repo(tmp_path: Path) -> tuple[Repo, Path]:
    root = tmp_path / "data-repo"
    repo = Repo.init(root)
    with repo.config_writer() as cfg:
        cfg.set_value("user", "name", "Test")
        cfg.set_value("user", "email", "test@example.invalid")
    repo.create_remote("origin", "https://example.invalid/data.git")
    db = root / "database" / "center.db"
    db.parent.mkdir(parents=True)
    return repo, db


def _commit(repo: Repo, db: Path, payload: bytes, message: str) -> str:
    db.write_bytes(payload)
    repo.index.add([str(db.relative_to(repo.working_tree_dir))])
    return repo.index.commit(message).hexsha


def test_plan_maps_every_ref_that_can_reach_plaintext_history(tmp_path, monkeypatch):
    repo, db = _repo(tmp_path)
    plain_sha = _commit(repo, db, SQLITE_HEADER + b"payload", "plain")
    repo.create_head("legacy", plain_sha)
    _commit(repo, db, b"CIPHERTEXT", "encrypted head")

    legacy_key = tmp_path / "database_key.dpapi"
    service_key = tmp_path / "service_database_key.dpapi"
    legacy_key.write_text("stub", encoding="utf-8")
    service_key.write_text("stub", encoding="utf-8")

    class _FakeKeyStore:
        def __init__(self, *args, **kwargs):
            self.bundle_path = legacy_key

    monkeypatch.setattr(planner, "DatabaseKeyStore", _FakeKeyStore)
    monkeypatch.setattr(
        planner,
        "get_protected_storage_layout",
        lambda: SimpleNamespace(key_bundle_path=service_key),
    )

    plan = planner.build_plan(Path(repo.working_tree_dir))

    assert plan.working_tree_clean is True
    assert plan.has_origin is True
    assert plan.reachable_plaintext_versions == 1
    assert plan.destructive_cutover_required is True
    assert "refs/heads/main" in plan.plaintext_refs
    assert "refs/heads/legacy" in plan.plaintext_refs
    assert "PLAINTEXT_GIT_HISTORY_PRESENT" in plan.blockers
    assert "WORKSPACE_KEY_NOT_PROVISIONED" not in plan.blockers
    assert "SERVICE_KEY_NOT_PROVISIONED" not in plan.blockers
    assert plan.ready_to_execute_cutover is False


def test_plan_reports_missing_key_enrollment_as_separate_blockers(tmp_path, monkeypatch):
    repo, db = _repo(tmp_path)
    _commit(repo, db, b"CIPHERTEXT", "encrypted")

    legacy_key = tmp_path / "missing-legacy-key"
    service_key = tmp_path / "missing-service-key"

    class _FakeKeyStore:
        def __init__(self, *args, **kwargs):
            self.bundle_path = legacy_key

    monkeypatch.setattr(planner, "DatabaseKeyStore", _FakeKeyStore)
    monkeypatch.setattr(
        planner,
        "get_protected_storage_layout",
        lambda: SimpleNamespace(key_bundle_path=service_key),
    )

    plan = planner.build_plan(Path(repo.working_tree_dir))

    assert plan.reachable_plaintext_versions == 0
    assert plan.destructive_cutover_required is False
    assert "WORKSPACE_KEY_NOT_PROVISIONED" in plan.blockers
    assert "SERVICE_KEY_NOT_PROVISIONED" in plan.blockers


def test_planner_runs_directly_without_pythonpath(tmp_path):
    repo, db = _repo(tmp_path)
    _commit(repo, db, SQLITE_HEADER + b"payload", "plain")

    center_root = Path(__file__).resolve().parents[1]
    script = center_root / "scripts" / "plan_sec01_encrypted_cutover.py"
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    completed = subprocess.run(
        [sys.executable, str(script), "--repo", str(repo.working_tree_dir)],
        cwd=str(center_root),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 10
    assert "ModuleNotFoundError" not in completed.stderr
    assert "Reachable plaintext DB versions: 1" in completed.stdout
    assert "Destructive cutover required: True" in completed.stdout
