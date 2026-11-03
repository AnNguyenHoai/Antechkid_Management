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
    from centermanager.database import session as session_module
    monkeypatch.setattr(session_module, "quiesce_runtime_db", lambda: None)
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


def test_interrupted_install_replays_verified_old_files_before_git_start(snapshot):
    sync, root = snapshot
    (root / "Database" / "center.db-wal").write_bytes(b"OLD-WAL")
    sync._begin_startup_install()
    marker = sync._startup_install_marker_path()
    import json
    record = json.loads(marker.read_text(encoding="utf-8"))
    assert record["format"] == 2 and record["state"] == "INSTALL_PENDING"

    (root / "Database" / "center.db").write_bytes(b"HALF-INSTALLED")
    (root / "Database" / "center.db-wal").unlink()
    (root / "Attachments" / "Employees" / "photo.txt").write_bytes(b"HALF-ATTACH")
    (root / "manifest.json").write_text('{"runtime_version": 999}')
    (root / "metadata" / "version.json").write_text('{"platform_version": ')
    restarted = StartupSynchronization.__new__(StartupSynchronization)
    restarted._runtime_db_path = sync._runtime_db_path
    restarted._paths = sync._paths
    restarted._runtime_manifest_path = sync._runtime_manifest_path
    restarted._metadata_dir = sync._metadata_dir
    assert restarted._check_interrupted_startup_install()
    assert not marker.exists()
    assert (root / "Database" / "center.db").read_bytes() == b"DB-LOCAL"
    assert (root / "Database" / "center.db-wal").read_bytes() == b"OLD-WAL"
    assert (root / "Attachments" / "Employees" / "photo.txt").read_bytes() == b"PHOTO-LOCAL"
    assert (root / "manifest.json").read_text() == '{"runtime_version": 1}'
    assert (root / "metadata" / "version.json").read_text() == '{"platform_version": 1}'


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


def test_complete_failed_rollback_releases_marker_only_when_all_phases_clean(snapshot):
    sync, root = snapshot
    sync._begin_startup_install()
    sync._startup_assets = ([("pending", "backup", True)], None)
    sync._startup_previous_local_oid = "a" * 40
    sync._complete_failed_startup_rollback()
    assert sync._startup_install_marker_path().exists()
    sync._startup_assets = None
    sync._startup_previous_local_oid = None
    sync._complete_failed_startup_rollback()
    assert not sync._startup_install_marker_path().exists()


def test_failed_rollback_retains_marker_if_db_generation_still_pending(snapshot):
    sync, root = snapshot
    sync._begin_startup_install()
    sync._startup_db_install_backup = ("dest", "backup", True, ())
    sync._complete_failed_startup_rollback()
    assert sync._startup_install_marker_path().exists()


def test_interrupted_replay_corrupted_backup_blocks_without_changing_local(snapshot):
    sync, root = snapshot
    sync._begin_startup_install()
    marker = sync._startup_install_marker_path()
    import json
    token = json.loads(marker.read_text(encoding="utf-8"))["transaction_id"]
    saved_db = marker.parent / "startup-replay" / token / "0" / "__file__"
    saved_db.write_bytes(b"CORRUPTED-BACKUP")
    (root / "Database" / "center.db").write_bytes(b"HALF-INSTALLED")
    assert not sync._check_interrupted_startup_install()
    assert marker.exists()
    assert (root / "Database" / "center.db").read_bytes() == b"HALF-INSTALLED"


def test_interrupted_replay_refuses_incompatible_runtime_target(snapshot):
    sync, root = snapshot
    sync._begin_startup_install()
    other = StartupSynchronization.__new__(StartupSynchronization)
    other._runtime_db_path = sync._runtime_db_path
    other._paths = SimpleNamespace(attachment_dir=root / "other-attachments")
    other._runtime_manifest_path = sync._runtime_manifest_path
    other._metadata_dir = sync._metadata_dir
    assert not other._check_interrupted_startup_install()
    assert sync._startup_install_marker_path().exists()


def test_replay_is_not_authoritative_without_subsequent_git_fetch(snapshot):
    """Restored LOCAL files cannot authorize login while Git MAIN is offline."""
    sync, root = snapshot
    sync._begin_startup_install()
    marker = sync._startup_install_marker_path()
    (root / "Database" / "center.db").write_bytes(b"HALF-DB")
    (root / "repository" / ".git").mkdir()
    sync._provider = SimpleNamespace(connect=lambda: True)
    sync._fetch_remote = lambda: False
    sync._prepare_authoritative_startup_replacement = lambda: (
        _ for _ in ()
    ).throw(AssertionError("Must not accept old local snapshot"))
    assert sync.run() is False
    assert not marker.exists()  # Replay completed, but startup still denied.
    assert (root / "Database" / "center.db").read_bytes() == b"DB-LOCAL"


def test_missing_old_wal_is_removed_on_interrupted_replay(snapshot):
    sync, root = snapshot
    sync._begin_startup_install()
    wal = root / "Database" / "center.db-wal"
    wal.write_bytes(b"UNACCEPTED-MAIN-WAL")
    assert sync._check_interrupted_startup_install()
    assert not wal.exists()
