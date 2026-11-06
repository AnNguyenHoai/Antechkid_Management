"""STARTUP-FIX-01 P4: deterministically exercise reconnect and read-only boundaries."""
from types import SimpleNamespace

import pytest

from centermanager.platform.sync.offline_read_state import (
    offline_read_active, set_offline_read,
)
from centermanager.platform.sync.runtime_sync_service import RuntimeSyncService
from centermanager.database import migration


@pytest.mark.parametrize("healthy,expected_syncs", [
    (False, 0), (True, 1),
])
def test_offline_poll_never_enters_normal_version_check_and_only_retries_healthy_git(
    monkeypatch, healthy, expected_syncs,
):
    from centermanager.platform.sync import runtime_sync_service
    calls = []
    fake = SimpleNamespace(_running=True, _poll_interval=30)
    fake._sync_manager = SimpleNamespace(
        provider=lambda: SimpleNamespace(health=lambda: healthy),
    )
    fake._perform_sync = lambda: calls.append("remote-to-local")
    fake._perform_check = lambda: pytest.fail("version-only check used in offline mode")
    monkeypatch.setattr(runtime_sync_service.time, "sleep", lambda _: setattr(fake, "_running", False))
    try:
        set_offline_read(True)
        RuntimeSyncService._sync_loop(fake)
        assert calls == ["remote-to-local"] * expected_syncs
        assert offline_read_active()
    finally:
        set_offline_read(False)


def test_offline_schema_check_never_attempts_migration_even_on_mismatch(monkeypatch):
    calls = []
    class Engine:
        def connect(self):
            class ConnectionContext:
                def __enter__(self): return object()
                def __exit__(self, *args): return False
            return ConnectionContext()
        def dispose(self): calls.append("dispose")
    monkeypatch.setattr(migration, "create_production_engine", lambda: Engine())
    monkeypatch.setattr(migration, "get_alembic_config", lambda _: object())
    monkeypatch.setattr(migration, "get_database_path", lambda: "local-cache")
    def incompatible(*args):
        calls.append("validate")
        raise RuntimeError("migration required")
    monkeypatch.setattr(migration, "_validate_post_upgrade_schema", incompatible)
    with pytest.raises(RuntimeError, match="migration required"):
        migration.verify_runtime_schema_readonly()
    assert calls == ["validate", "dispose"]


def test_offline_reconnect_never_creates_production_income_or_git_push_paths():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "src" / "centermanager"
    reconnect = (root / "platform" / "sync" / "authoritative_runtime_sync_service.py").read_text(encoding="utf-8")
    reconnect_body = reconnect.split("def _perform_sync(", 1)[1]
    assert "self._sync_manager.begin_sync()" in reconnect_body
    assert 'begin_sync("Auto sync"' not in reconnect_body
    assert "self._apply_runtime_update()" in reconnect_body
    assert "provider.observe_remote_main_commit()" in reconnect_body
    assert "WriteRecoveryJournal().assert_replaceable()" in reconnect_body
    assert "set_offline_read(False)" in reconnect_body
    assert reconnect_body.index("WriteRecoveryJournal().assert_replaceable()") < reconnect_body.index("set_offline_read(False)")


def test_phase1_probe_never_uses_remote_git_fetch_or_migration():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "src" / "centermanager"
    gate = (root / "platform" / "sync" / "offline_read_gate.py").read_text(encoding="utf-8")
    assert ".fetch(" not in gate
    assert "command.upgrade(" not in gate
    assert "record_synchronized(" not in gate
    assert "reconcile(" not in gate
    assert "validate_identity(" in gate
    assert "journal.assert_replaceable()" in gate
