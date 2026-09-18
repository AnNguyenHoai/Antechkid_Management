# -*- coding: utf-8 -*-
"""A4.3 regression contracts for Git-authoritative synchronization."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_runtime_sync_rejects_missing_authoritative_database():
    source = _read("src/centermanager/platform/sync/runtime_sync_service.py")
    block = source[source.index("    def _apply_runtime_update"):source.index("    def _refresh_db_sessions")]
    assert "Repository database not found" in block
    assert "return False" in block
    assert "return True" not in block.split("repo_db.exists()", 1)[-1]


def test_runtime_sync_only_reports_success_after_runtime_materialization():
    source = _read("src/centermanager/platform/sync/runtime_sync_service.py")
    apply_pos = source.index("apply_success = self._apply_runtime_update()")
    complete_pos = source.index("self._event_bus.publish(SynchronizationCompleted(", apply_pos)
    assert apply_pos < complete_pos
    assert 'raise RuntimeError("Authoritative repository database could not be materialized into runtime")' in source[apply_pos:complete_pos]


def test_publish_does_not_continue_after_failed_repository_pull():
    source = _read("src/centermanager/platform/synchronization/git_synchronization_provider.py")
    start = source.index("    def publish(self, message: str, user: str) -> bool:")
    end = source.index("    def publish_only(", start)
    block = source[start:end]
    assert "if not self.pull()" in block
    assert "Unable to synchronize repository before publish" in block
    assert block.index("if not self.pull()") < block.index("self._sync_employee_attachments_to_repository()")


def test_publish_only_always_establishes_remote_commit_fence():
    source = _read("src/centermanager/platform/synchronization/git_synchronization_provider.py")
    start = source.index("    def publish_only(")
    end = source.index("    def status(", start)
    block = source[start:end]
    assert '["ls-remote", "origin", f"refs/heads/{self._branch}"]' in block
    assert "if expected_main_commit is None:" in block
    assert "--force-with-lease={self._branch}:{expected_remote_commit}" in source


def test_background_sync_materializes_repository_database():
    source = _read("src/centermanager/platform/runtime/background_sync.py")
    start = source.index("    def _reload_runtime")
    block = source[start:]
    assert "repository" in block
    assert '/"database" / "center.db"' in block
    assert 'paths.database_dir / "center.db"' in block
    assert "refresh_runtime_db()" in block
    assert "return False" in block
    assert "VersionUpdated" in block


def test_background_sync_never_reports_runtime_refresh_without_database_materialization():
    source = _read("src/centermanager/platform/runtime/background_sync.py")
    materialize = source.index("with open(repo_db, \"rb\")")
    refresh = source.index("refresh_runtime_db()", materialize)
    notify = source.index("notification_service.notify", refresh)
    assert materialize < refresh < notify


def test_source_of_truth_paths_are_explicit():
    startup = _read("src/centermanager/platform/sync/startup_sync.py")
    runtime_sync = _read("src/centermanager/platform/sync/runtime_sync_service.py")
    background = _read("src/centermanager/platform/runtime/background_sync.py")
    expected = 'runtime_root / "repository" / "database" / "center.db"'
    assert expected in startup
    assert expected in runtime_sync
    assert expected in background


def test_restart_startup_path_remains_repository_to_runtime():
    source = _read("src/centermanager/platform/sync/startup_sync.py")
    apply_pos = source.index("if not self._apply_runtime_database():")
    copy_pos = source.index("with open(repo_db, 'rb')", source.index("def _apply_runtime_database"))
    assert apply_pos < copy_pos
