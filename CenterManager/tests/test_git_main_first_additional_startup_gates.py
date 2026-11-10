"""Git MAIN first: do not lose unpublished Git/Employee/credential evidence.

Synthetic local fixtures only; never touch production repos or credentials.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.platform.sync.provisioning_secret_backup import (
    preserve_provisioning_secrets,
)
from centermanager.platform.sync.startup_sync import StartupSynchronization
from centermanager.platform.recovery_review_notices import RecoveryReviewNotices
from tests.test_e1b1_durable_write_recovery import (
    workspace, git, begin,
)  # noqa: F401


def test_dirty_git_worktree_moved_whole_before_main_reset(workspace):
    w = workspace
    begin(w)
    repo = w.journal.repository
    (repo / "untracked-review.txt").write_text("never-published", encoding="utf-8")
    git(repo, "commit", "--allow-empty", "-m", "unpublished-local-only-commit")
    local_before = git(repo, "rev-parse", "HEAD")
    assert local_before != w.base
    assert w.provider.fetch()
    accepted = w.provider.get_fetched_remote_main_commit()
    assert accepted == w.base

    assert w.provider.reset_verified_main_for_review(accepted)
    archive = Path(w.provider._startup_review_git_archive)
    assert (archive / "untracked-review.txt").read_text(encoding="utf-8") == "never-published"
    assert git(archive, "rev-parse", "HEAD") == local_before
    assert not (repo / "untracked-review.txt").exists()
    assert git(repo, "rev-parse", "HEAD") == accepted
    assert w.provider.observe_remote_main_commit() == accepted
    # The old Git history and files are never pushed or destroyed.
    assert archive.is_dir()


def test_clean_git_fast_forward_does_not_archive_redundant_worktree(workspace, tmp_path):
    w = workspace
    import subprocess
    import shutil
    repo = w.journal.repository
    other = tmp_path / "independent-git-writer"
    subprocess.run(
        ["git", "clone", "-b", "main", str(w.remote), str(other)],
        check=True, capture_output=True,
    )
    git(other, "config", "user.name", "Independent Writer")
    git(other, "config", "user.email", "synthetic@example.invalid")
    (other / "remote-only.txt").write_text("accepted", encoding="utf-8")
    git(other, "add", "remote-only.txt")
    git(other, "commit", "-m", "external remote MAIN change")
    git(other, "push", "origin", "main")
    assert w.provider.fetch()
    accepted = w.provider.get_fetched_remote_main_commit()
    assert accepted != w.base

    assert w.provider.reset_verified_main_for_review(accepted)
    assert git(repo, "rev-parse", "HEAD") == accepted
    assert (repo / "remote-only.txt").read_text(encoding="utf-8") == "accepted"
    assert not hasattr(w.provider, "_startup_review_git_archive")


def test_review_startup_assets_move_without_copying_deep_local_files(tmp_path, monkeypatch):
    root = tmp_path / "runtime"
    old = root / "Attachments" / "Employees"
    old.mkdir(parents=True)
    folder = old / "exports" / ("a" * 65) / ("b" * 65)
    folder.mkdir(parents=True)
    (folder / "lesson.txt").write_text("unpublished", encoding="utf-8")
    (root / "metadata").mkdir()
    (root / "metadata" / "version.json").write_text("{}", encoding="utf-8")
    (root / "manifest.json").write_text("{}", encoding="utf-8")
    repo = root / "repository"
    (repo / "Attachments" / "Employees").mkdir(parents=True)
    (repo / "Attachments" / "Employees" / "official.txt").write_text("git-main", encoding="utf-8")
    startup = StartupSynchronization.__new__(StartupSynchronization)
    startup._runtime_db_path = root / "Database" / "center.db"
    startup._paths = SimpleNamespace(attachment_dir=root / "Attachments")
    startup._metadata_dir = root / "metadata"
    startup._runtime_manifest_path = root / "manifest.json"
    startup._repo_path = repo
    startup._review_only_reset_requested = True
    import shutil
    old_copytree = shutil.copytree
    def reject_legacy_copy(src, *a, **k):
        if str(src).startswith(str(old)):
            raise AssertionError("Old Employee tree must never be copied recursively")
        return old_copytree(src, *a, **k)
    monkeypatch.setattr(shutil, "copytree", reject_legacy_copy)
    startup._prepare_startup_assets()
    saved = startup._startup_assets
    assert saved is not None
    assert not old.exists()
    assert (saved[0][0][1] / "exports" / ("a" * 65)
            / ("b" * 65) / "lesson.txt").read_text(encoding="utf-8") == "unpublished"
    startup._sync_employee_attachments_from_repository()
    assert (old / "official.txt").read_text(encoding="utf-8") == "git-main"
    startup._finalize_startup_assets()
    assert (saved[0][0][1] / "exports" / ("a" * 65)
            / ("b" * 65) / "lesson.txt").exists()


def test_secret_backup_is_fixed_scope_not_recovery_capture(tmp_path):
    root = tmp_path / "runtime.write-recovery"
    (root / "captures" / "nested").mkdir(parents=True)
    (root / "captures" / "nested" / "old.txt").write_text("do not traverse", encoding="utf-8")
    key = tmp_path / "runtime" / "Config" / "database_key.dpapi"
    key.parent.mkdir(parents=True)
    key.write_bytes(b"synthetic-machine-secret")
    config = key.parent / "config.json"
    config.write_text('{"synthetic":true}', encoding="utf-8")
    archive = preserve_provisioning_secrets(
        recovery_root=root, key_bundle=key, config_file=config,
    )
    assert (archive / "database-key.dpapi").read_bytes() == key.read_bytes()
    assert (archive / "config.json").read_bytes() == config.read_bytes()
    assert list(archive.iterdir()) and len(list(archive.iterdir())) == 2
    assert (root / "captures" / "nested" / "old.txt").is_file()


def test_corrupt_interrupted_marker_does_not_veto_future_main(tmp_path, monkeypatch):
    root = tmp_path / "runtime"
    db = root / "Database" / "center.db"
    db.parent.mkdir(parents=True)
    db.write_bytes(b"old-local-not-authoritative")
    marker = tmp_path / "runtime.write-recovery" / "startup-install.pending.json"
    marker.parent.mkdir()
    marker.write_bytes(b"{corrupted old marker")
    from centermanager.database import session as session_module
    monkeypatch.setattr(session_module, "quiesce_runtime_db", lambda: None)
    monkeypatch.setattr(session_module, "end_runtime_db_maintenance", lambda: None)
    startup = StartupSynchronization.__new__(StartupSynchronization)
    startup._runtime_db_path = db
    startup._paths = SimpleNamespace(attachment_dir=root / "Attachments")
    startup._metadata_dir = root / "metadata"
    startup._runtime_manifest_path = root / "manifest.json"
    assert startup._check_interrupted_startup_install()
    assert not marker.exists()
    assert startup._interrupted_install_review_marker.read_bytes() == b"{corrupted old marker"
    assert db.read_bytes() == b"old-local-not-authoritative"


def test_modern_notice_only_covers_exact_old_session(tmp_path):
    root = tmp_path / "runtime.write-recovery"
    root.mkdir()
    journal_file = root / "journal.json"
    journal_file.write_text('{"session_id":"session-a","status":"OPEN"}', encoding="utf-8")
    journal = SimpleNamespace(root=root, journal=journal_file, runtime=tmp_path / "runtime")
    notices = RecoveryReviewNotices(journal)
    path = notices.record(observed_main_oid="a" * 40)
    notices.acknowledge(path.stem)
    assert notices.covers_legacy_case({"write_session_id": "session-a"})
    assert not notices.covers_legacy_case({"write_session_id": "session-b"})
    assert not notices.covers_legacy_case({"write_session_id": None})


def test_failure_does_not_restore_old_unpublished_commit_over_main(tmp_path):
    startup = StartupSynchronization.__new__(StartupSynchronization)
    def forbid_reset(_args):
        raise AssertionError("old unpublished commit must not overwrite MAIN")
    startup._provider = SimpleNamespace(
        _startup_review_git_archive=str(tmp_path / "git-worktrees" / "old"),
        _run_git_command=forbid_reset,
    )
    startup._startup_previous_local_oid = "a" * 40
    startup._rollback_startup_git_repository()
    assert startup._startup_previous_local_oid is None
