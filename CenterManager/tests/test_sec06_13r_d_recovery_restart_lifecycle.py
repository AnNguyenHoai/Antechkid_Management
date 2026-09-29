from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "src" / "centermanager"


def _read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


def test_recovery_ui_marks_success_and_publish_incomplete_as_restart_required():
    source = _read("ui/admin_workspace/backup_recovery_page.py")
    assert "recovery_restart_required = Signal(str)" in source
    assert "if result.success:" in source
    assert "Recovery committed. Restart is required before further use." in source
    assert 'if "authoritative recovery publish" in str(error).lower():' in source
    assert "Recovery publish was incomplete. Restart is required" in source


def test_admin_recovery_uses_live_runtime_sync_service_not_second_sync_manager():
    source = _read("ui/admin_workspace/admin_workspace_shell.py")
    assert "def _live_sync_service(self):" in source
    assert 'getattr(self.window(), "_sync_service", None)' in source
    assert "AuthoritativeRecoveryPublisher(self._live_sync_service)" in source


def test_recovery_publisher_resolves_service_at_publish_time_and_fails_closed():
    source = _read("platform/backup/recovery_publisher.py")
    assert "def _runtime_sync(self):" in source
    assert "runtime_sync = self._runtime_sync()" in source
    assert 'RecoveryPublishError("Recovery publisher is unavailable.")' in source


def test_next_startup_reestablishes_remote_authoritative_runtime():
    source = _read("platform/sync/startup_sync.py")
    reset = source.index("if not self._reset_to_remote():")
    preflight = source.index("if not self._preflight_authoritative_database():")
    apply_runtime = source.index("if not self._apply_runtime_database():")
    refresh = source.index("if not self._refresh_database_sessions():")
    assert reset < preflight < apply_runtime < refresh
