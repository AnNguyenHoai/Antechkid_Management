"""STARTUP-FIX-01 Phase 2: offline read-only startup and WRITE gate."""
from pathlib import Path

from centermanager.platform.sync.offline_read_state import (
    offline_read_active, set_offline_read,
)
from centermanager.platform.collaboration.collaboration_manager import (
    CollaborationManager, WriteRequestResult,
)


ROOT = Path(__file__).resolve().parents[1] / "src" / "centermanager"


def test_global_offline_read_gate_blocks_write_before_remote_operations():
    try:
        set_offline_read(True)
        result = CollaborationManager.request_write(object(), "finance")
        assert result.result == WriteRequestResult.ERROR
        assert "Offline READ" in result.message
    finally:
        set_offline_read(False)


def test_online_is_unaffected_by_global_offline_state():
    try:
        set_offline_read(False)
        assert not offline_read_active()
        set_offline_read(True)
        assert offline_read_active()
    finally:
        set_offline_read(False)


def test_bootstrap_only_falls_back_after_remote_fetch_failure():
    source = (ROOT / "platform" / "bootstrap" / "bootstrap_manager.py").read_text(encoding="utf-8")
    startup = (ROOT / "platform" / "sync" / "startup_sync.py").read_text(encoding="utf-8")
    assert "if not startup.remote_unavailable:" in source
    assert "eligibility = assess_offline_read(paths)" in source
    assert "if not eligibility.allowed:" in source
    assert "set_offline_read(True)" in source
    assert "self.remote_unavailable = True" in startup


def test_offline_does_not_migrate_shared_database_or_trigger_daily_side_effects():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    migration = (ROOT / "database" / "migration.py").read_text(encoding="utf-8")
    # Offline READ and Recovery advisory startup both must select the
    # read-only schema verifier, not writable Alembic migration. Test the
    # actual helper contract rather than the old inline if-statement.
    assert "offline_read=bootstrap._offline_read" in source
    assert "_validate_accepted_runtime_schema(readonly=use_readonly_schema)" in source
    assert "verify_runtime_schema_readonly()" in source
    assert "if not bootstrap._offline_read:" in source
    assert "def verify_runtime_schema_readonly()" in migration
    method = migration.split("def verify_runtime_schema_readonly()", 1)[1].split(
        "def _bundled_root()", 1
    )[0]
    assert "_validate_post_upgrade_schema(" in method
    assert "command.upgrade(" not in method
    assert "command.stamp(" not in method


def test_offline_ui_has_disabled_write_button_and_direct_handler_guard():
    source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert 'self.start_edit_btn.setText("Offline - READ only")' in source
    assert "if offline_read_active():" in source
    assert "self.start_edit_btn.setEnabled(False)" in source


def test_offline_recovery_does_not_turn_other_bootstrap_failure_into_read():
    source = (ROOT / "platform" / "bootstrap" / "bootstrap_manager.py").read_text(encoding="utf-8")
    assert "if not startup.remote_unavailable:" in source
    assert "if not eligibility.allowed:" in source
    assert "RuntimeState.OFFLINE if getattr(self, '_offline_read', False) else RuntimeState.READY" in source
