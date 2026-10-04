from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / "src" / "centermanager" / "platform" / "sync"


def _source(name: str) -> str:
    return (SYNC / name).read_text(encoding="utf-8")


def test_public_runtime_sync_uses_authoritative_main_barrier():
    source = _source("__init__.py")
    assert "from .authoritative_runtime_sync_service import RuntimeSyncService" in source


def test_write_handoff_always_resets_to_remote_before_runtime_install():
    source = _source("authoritative_runtime_sync_service.py")
    method = source.split("def execute_write_handoff_sync", 1)[1].split("def _perform_sync", 1)[0]
    force_pos = method.index("self._force_latest_main_repository()")
    install_pos = method.index("self._apply_runtime_update()")
    ui_pos = method.index("self._write_handoff_ui_refresh.refresh()")
    assert force_pos < install_pos < ui_pos
    # Manifest-version equality must never be allowed to select the handoff source.
    assert "remote_version >" not in method
    assert "remote_version ==" not in method


def test_authoritative_barrier_verifies_exact_git_commit_identity():
    source = _source("authoritative_runtime_sync_service.py")
    barrier = source.split("def _force_latest_main_repository", 1)[1].split("def execute_write_handoff_sync", 1)[0]
    assert "reset_to_remote()" in barrier
    assert "get_remote()" in barrier
    assert "get_local()" in barrier
    assert "local_commit != remote_commit" in barrier


def test_background_sync_is_pull_only_and_cannot_publish_stale_runtime():
    source = _source("authoritative_runtime_sync_service.py")
    method = source.split("def _perform_sync", 1)[1]
    assert "self._sync_manager.begin_sync()" in method
    assert 'begin_sync("Auto sync"' not in method
    assert "publish_only(" not in method
    assert "materialize_runtime_database_to_repository" not in method


def test_handoff_rechecks_main_after_materialization_before_ui_grant():
    source = _source("authoritative_runtime_sync_service.py")
    method = source.split("def execute_write_handoff_sync", 1)[1].split("def _perform_sync", 1)[0]
    install_pos = method.index("self._apply_runtime_update()")
    recheck_pos = method.index("remote_after = provider.get_remote_main_commit()")
    ui_pos = method.index("self._write_handoff_ui_refresh.refresh()")
    assert install_pos < recheck_pos < ui_pos
    assert "remote_after != authoritative_commit" in method
    assert "local_after != authoritative_commit" in method
