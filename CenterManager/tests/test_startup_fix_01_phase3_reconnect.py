"""STARTUP-FIX-01 P3: reconnect remains fenced until MAIN/runtime accepted."""
import threading
from types import SimpleNamespace

import pytest

from centermanager.platform.sync.authoritative_runtime_sync_service import RuntimeSyncService
from centermanager.platform.sync.offline_read_state import (
    offline_read_active, set_offline_read,
)
from centermanager.platform.runtime.context.runtime_state import RuntimeState


def _fake_reconnect(monkeypatch, *, observed):
    import centermanager.platform.write_recovery as recovery
    verified = []
    monkeypatch.setattr(
        recovery, "WriteRecoveryJournal",
        lambda: SimpleNamespace(assert_replaceable=lambda: verified.append("clean")),
    )
    events = []
    runtime_state = SimpleNamespace(current=RuntimeState.OFFLINE)
    runtime_state.transition_to = lambda state: setattr(runtime_state, "current", state)
    provider = SimpleNamespace(
        get_local_main_commit=lambda: "a" * 40,
        observe_remote_main_commit=lambda: observed,
    )
    result = SimpleNamespace(is_success=lambda: True)
    fake = SimpleNamespace(
        _state_mutex=threading.RLock(),
        _set_status=lambda status: None,
        _sync_manager=SimpleNamespace(
            begin_sync=lambda: result, provider=lambda: provider,
        ),
        _apply_runtime_update=lambda: True,
        _get_repository_version=lambda: 1,
        _current_version=1,
        _remote_version=1,
        _pending_update=False,
        _last_sync=None,
        _failed_count=0,
        _context_manager=SimpleNamespace(
            get_context=lambda: SimpleNamespace(runtime=SimpleNamespace(state=runtime_state))
        ),
        _collab_manager=SimpleNamespace(
            get_session=lambda: SimpleNamespace(session_id="testing"),
        ),
        _event_bus=SimpleNamespace(publish=lambda event: events.append(event)),
    )
    return fake, runtime_state, events, verified


def test_reconnect_rejects_remote_main_oid_race(monkeypatch):
    try:
        set_offline_read(True)
        fake, state, events, verified = _fake_reconnect(monkeypatch, observed="b" * 40)
        assert RuntimeSyncService._perform_sync(fake) is False
        assert offline_read_active()
        assert state.current is RuntimeState.OFFLINE
        assert not verified
        assert not events
    finally:
        set_offline_read(False)


def test_only_verified_remote_main_and_clean_receipt_unlock_write(monkeypatch):
    from centermanager.platform.collaboration.events import ModeChanged
    try:
        set_offline_read(True)
        fake, state, events, verified = _fake_reconnect(monkeypatch, observed="a" * 40)
        assert RuntimeSyncService._perform_sync(fake) is True
        assert verified == ["clean"]
        assert not offline_read_active()
        assert state.current is RuntimeState.READY
        assert any(isinstance(e, ModeChanged) and e.mode == "READ" for e in events)
    finally:
        set_offline_read(False)


def test_failed_runtime_install_cannot_unlock_offline(monkeypatch):
    try:
        set_offline_read(True)
        fake, state, events, verified = _fake_reconnect(monkeypatch, observed="a" * 40)
        fake._apply_runtime_update = lambda: False
        assert RuntimeSyncService._perform_sync(fake) is False
        assert offline_read_active()
        assert state.current is RuntimeState.OFFLINE
        assert not verified
    finally:
        set_offline_read(False)


def test_background_reconnect_does_not_require_version_increment():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "src" / "centermanager"
    base = (root / "platform" / "sync" / "runtime_sync_service.py").read_text(encoding="utf-8")
    body = base.split("def _sync_loop(", 1)[1].split("def _get_repository_version(", 1)[0]
    assert "offline_read_active()" in body
    assert "provider.health()" in body
    assert "self._perform_sync()" in body
    assert body.index("offline_read_active()") < body.index("self._perform_check()")


def test_reconnect_keeps_write_fence_until_verified_clean_runtime():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "src" / "centermanager"
    service = (root / "platform" / "sync" / "authoritative_runtime_sync_service.py").read_text(encoding="utf-8")
    reconnect = service.split("def _perform_sync(", 1)[1]
    assert reconnect.index("self._apply_runtime_update()") < reconnect.index("provider.observe_remote_main_commit()")
    assert reconnect.index("WriteRecoveryJournal().assert_replaceable()") < reconnect.index("set_offline_read(False)")
    assert 'ModeChanged(mode="READ")' in reconnect
