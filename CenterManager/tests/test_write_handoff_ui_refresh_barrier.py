# -*- coding: utf-8 -*-

import pytest

from centermanager.platform.sync.runtime_sync_service import (
    RuntimeSyncService as BaseRuntimeSyncService,
)
from centermanager.platform.sync.write_handoff_runtime_sync_service import (
    RuntimeSyncService,
)


class _Barrier:
    def __init__(self, result=True):
        self.result = result
        self.calls = 0

    def refresh(self):
        self.calls += 1
        return self.result


def _service_with_barrier(result=True):
    service = object.__new__(RuntimeSyncService)
    service._write_handoff_ui_refresh = _Barrier(result)
    return service


def test_write_handoff_refreshes_ui_only_after_authoritative_sync(monkeypatch):
    service = _service_with_barrier(True)
    order = []

    def authoritative_sync(_self):
        order.append("authoritative-sync")
        return True

    def ui_refresh():
        order.append("ui-refresh")
        service._write_handoff_ui_refresh.calls += 1
        return True

    monkeypatch.setattr(
        BaseRuntimeSyncService,
        "execute_write_handoff_sync",
        authoritative_sync,
    )
    service._write_handoff_ui_refresh.refresh = ui_refresh

    assert service.execute_write_handoff_sync() is True
    assert order == ["authoritative-sync", "ui-refresh"]


def test_write_handoff_fails_closed_when_ui_refresh_fails(monkeypatch):
    service = _service_with_barrier(False)
    monkeypatch.setattr(
        BaseRuntimeSyncService,
        "execute_write_handoff_sync",
        lambda _self: True,
    )

    assert service.execute_write_handoff_sync() is False
    assert service._write_handoff_ui_refresh.calls == 1


def test_write_handoff_does_not_refresh_ui_when_authoritative_sync_fails(monkeypatch):
    service = _service_with_barrier(True)
    monkeypatch.setattr(
        BaseRuntimeSyncService,
        "execute_write_handoff_sync",
        lambda _self: False,
    )

    assert service.execute_write_handoff_sync() is False
    assert service._write_handoff_ui_refresh.calls == 0


def test_database_session_refresh_failure_propagates(monkeypatch):
    service = object.__new__(RuntimeSyncService)

    def fail_refresh():
        raise RuntimeError("session refresh failed")

    monkeypatch.setattr(
        "centermanager.database.session.refresh_runtime_db",
        fail_refresh,
    )

    with pytest.raises(RuntimeError, match="session refresh failed"):
        service._refresh_db_sessions()
