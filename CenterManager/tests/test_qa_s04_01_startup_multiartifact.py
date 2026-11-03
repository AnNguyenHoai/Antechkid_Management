"""QA-S04-01: Git MAIN snapshot must not mix DB, attachments and manifest.

Disposable synthetic bytes only. These tests deliberately expose the current
non-atomic startup copy boundary. They are release-gating assertions, not
production data operations.
"""
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.platform.sync.startup_sync import StartupSynchronization


@pytest.fixture
def snapshot(tmp_path, monkeypatch):
    import centermanager.platform.write_recovery as recovery

    root = tmp_path / "runtime"
    repo = root / "repository"
    (repo / "database").mkdir(parents=True)
    (repo / "Attachments" / "Employees").mkdir(parents=True)
    (root / "Database").mkdir(parents=True)
    (root / "Attachments" / "Employees").mkdir(parents=True)
    (root / "metadata").mkdir(parents=True)

    (repo / "database" / "center.db").write_bytes(b"DB-MAIN")
    (root / "Database" / "center.db").write_bytes(b"DB-LOCAL")
    (repo / "Attachments" / "Employees" / "photo.txt").write_bytes(b"PHOTO-MAIN")
    (root / "Attachments" / "Employees" / "photo.txt").write_bytes(b"PHOTO-LOCAL")
    (repo / "manifest.json").write_text('{"runtime_version": 2}', encoding="utf-8")
    (root / "manifest.json").write_text('{"runtime_version": 1}', encoding="utf-8")
    (root / "metadata" / "version.json").write_text(
        '{"platform_version": 1}', encoding="utf-8"
    )

    monkeypatch.setattr(recovery, "require_replaceable", lambda: None)
    sync = StartupSynchronization.__new__(StartupSynchronization)
    sync._repo_path = repo
    sync._runtime_db_path = root / "Database" / "center.db"
    sync._runtime_manifest_path = root / "manifest.json"
    sync._metadata_dir = root / "metadata"
    sync._paths = SimpleNamespace(attachment_dir=root / "Attachments")

    # Isolate the multi-artifact boundary from the independently tested
    # SQLCipher atomic installer; do not weaken its production checks.
    def install(repo_db):
        sync._runtime_db_path.write_bytes(repo_db.read_bytes())
        return True

    sync._install_authoritative_database_atomically = install
    sync._rollback_startup_database_install = lambda: sync._runtime_db_path.write_bytes(b"DB-LOCAL")
    return sync, root


def test_successful_snapshot_materializes_matching_main_artifacts(snapshot):
    sync, root = snapshot
    assert sync._apply_runtime_database()
    assert (root / "Database" / "center.db").read_bytes() == b"DB-MAIN"
    assert (root / "Attachments" / "Employees" / "photo.txt").read_bytes() == b"PHOTO-MAIN"
    assert '"runtime_version": 2' in (root / "manifest.json").read_text()
    assert '"platform_version": 2' in (root / "metadata" / "version.json").read_text()


def test_fault_during_attachment_copy_restores_old_snapshot(snapshot):
    sync, root = snapshot
    def partial_copy():
        employees = root / "Attachments" / "Employees"
        (employees / "photo.txt").write_bytes(b"HALF-COPIED")
        raise OSError("injected mid-copy failure")
    sync._sync_employee_attachments_from_repository = partial_copy

    assert sync._apply_runtime_database() is False
    assert (root / "Database" / "center.db").read_bytes() == b"DB-LOCAL"
    assert (root / "Attachments" / "Employees" / "photo.txt").read_bytes() == b"PHOTO-LOCAL"
    assert '"runtime_version": 1' in (root / "manifest.json").read_text()


def test_fault_during_metadata_update_restores_old_snapshot(snapshot, monkeypatch):
    sync, root = snapshot
    original = __import__("json").dump
    def fail_version_write(obj, stream, *args, **kwargs):
        if stream.name.endswith("metadata" + __import__("os").sep + "version.json"):
            stream.write('{"platform_version": ')
            raise OSError("injected partial metadata write")
        return original(obj, stream, *args, **kwargs)
    monkeypatch.setattr("centermanager.platform.sync.startup_sync.json.dump", fail_version_write)

    assert sync._apply_runtime_database() is False
    assert (root / "Database" / "center.db").read_bytes() == b"DB-LOCAL"
    assert (root / "Attachments" / "Employees" / "photo.txt").read_bytes() == b"PHOTO-LOCAL"
    assert '"runtime_version": 1' in (root / "manifest.json").read_text()
    assert '"platform_version": 1' in (root / "metadata" / "version.json").read_text()


def test_manifest_copy_error_rolls_back_all_artifacts(snapshot, monkeypatch):
    sync, root = snapshot
    import builtins
    real_open = builtins.open
    injected = {"done": False}

    def fail_manifest_write(path, mode="r", *args, **kwargs):
        if (str(path) == str(root / "manifest.json") and mode == "wb"
                and not injected["done"]):
            injected["done"] = True
            raise OSError("injected manifest install fault")
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", fail_manifest_write)
    assert sync._apply_runtime_database() is False
    assert (root / "Database" / "center.db").read_bytes() == b"DB-LOCAL"
    assert (root / "Attachments" / "Employees" / "photo.txt").read_bytes() == b"PHOTO-LOCAL"
    assert (root / "manifest.json").read_text() == '{"runtime_version": 1}'
    assert (root / "metadata" / "version.json").read_text() == '{"platform_version": 1}'


def test_staging_error_leaves_local_workspace_intact(snapshot, monkeypatch):
    sync, root = snapshot
    import shutil
    real_copytree = shutil.copytree

    def fail_stage(src, dst, *args, **kwargs):
        if str(src).endswith("repository/Attachments/Employees") or (
            Path(src).parts[-3:] == ("repository", "Attachments", "Employees")
        ):
            raise OSError("injected staging failure")
        return real_copytree(src, dst, *args, **kwargs)

    monkeypatch.setattr(shutil, "copytree", fail_stage)
    assert sync._apply_runtime_database() is False
    assert (root / "Database" / "center.db").read_bytes() == b"DB-LOCAL"
    assert (root / "Attachments" / "Employees" / "photo.txt").read_bytes() == b"PHOTO-LOCAL"
    assert (root / "manifest.json").read_text() == '{"runtime_version": 1}'


def test_failed_session_refresh_rolls_back_all_artifacts(snapshot):
    sync, root = snapshot
    old = (root / "Database" / "center.db").read_bytes()
    class Provider:
        def get_local_main_commit(self):
            return "1" * 40
        def _run_git_command(self, args):
            assert args == ["reset", "--hard", "1" * 40]
    sync._provider = Provider()
    sync._startup_previous_local_oid = "1" * 40
    sync._fetch_remote = lambda: True
    sync._prepare_authoritative_startup_replacement = lambda: True
    sync._reset_to_remote = lambda: True
    sync._preflight_authoritative_database = lambda: True
    sync._refresh_database_sessions = lambda: False
    sync._finalize_startup_database_install = lambda: None
    assert sync._apply_runtime_database()
    assert (root / "Database" / "center.db").read_bytes() == b"DB-MAIN"
    sync._rollback_startup_database_install()
    sync._rollback_startup_assets()
    sync._rollback_startup_git_repository()
    assert (root / "Database" / "center.db").read_bytes() == old
    assert (root / "Attachments" / "Employees" / "photo.txt").read_bytes() == b"PHOTO-LOCAL"
    assert '"runtime_version": 1' in (root / "manifest.json").read_text()
    assert '"platform_version": 1' in (root / "metadata" / "version.json").read_text()


def test_process_kill_marker_blocks_second_start_before_network_or_git(snapshot):
    """A killed process leaves its durable marker; restart must fail closed."""
    sync, root = snapshot
    sync._begin_startup_install()
    marker = sync._startup_install_marker_path()
    assert marker.is_file()
    import json
    assert json.loads(marker.read_text(encoding="utf-8"))["state"] == "INSTALL_PENDING"

    # New object simulates a new EXE process without in-memory rollback state.
    restarted = StartupSynchronization.__new__(StartupSynchronization)
    restarted._runtime_db_path = sync._runtime_db_path
    restarted._repo_path = sync._repo_path
    restarted._provider = SimpleNamespace(
        connect=lambda: (_ for _ in ()).throw(AssertionError("Git must not run"))
    )
    assert restarted.run() is False
    assert "Interrupted startup installation" in restarted.recovery_error
    assert marker.exists()


def test_successful_install_commit_clears_interruption_marker(snapshot):
    sync, root = snapshot
    sync._begin_startup_install()
    marker = sync._startup_install_marker_path()
    assert marker.exists()
    sync._complete_startup_install()
    assert not marker.exists()
    assert sync._check_interrupted_startup_install()


def test_truncated_interruption_marker_still_blocks_startup(snapshot):
    sync, root = snapshot
    marker = sync._startup_install_marker_path()
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('{"format":', encoding="utf-8")
    assert not sync._check_interrupted_startup_install()
    assert marker.read_text(encoding="utf-8") == '{"format":'
