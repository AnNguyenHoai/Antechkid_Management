# -*- coding: utf-8 -*-
"""Regression coverage for SEC06 production RuntimeSyncService wiring."""

from centermanager.ui.admin_workspace.admin_workspace_shell import AdminWorkspaceShell


def _runtime_sync_candidate():
    RuntimeSyncService = type("RuntimeSyncService", (), {"handoff": lambda self: True})
    return RuntimeSyncService()


def test_explicit_runtime_sync_service_wins():
    explicit = object()
    collaboration = type("Collaboration", (), {})()
    collaboration._write_handoff_guard = _runtime_sync_candidate().handoff

    resolved = AdminWorkspaceShell._resolve_runtime_sync_service(explicit, collaboration)

    assert resolved is explicit


def test_recovers_live_runtime_sync_service_from_write_handoff_guard():
    runtime_sync = _runtime_sync_candidate()
    collaboration = type("Collaboration", (), {})()
    collaboration._write_handoff_guard = runtime_sync.handoff

    resolved = AdminWorkspaceShell._resolve_runtime_sync_service(None, collaboration)

    assert resolved is runtime_sync


def test_does_not_accept_unrelated_bound_guard_owner():
    class OtherService:
        def handoff(self):
            return True

    other = OtherService()
    collaboration = type("Collaboration", (), {})()
    collaboration._write_handoff_guard = other.handoff

    resolved = AdminWorkspaceShell._resolve_runtime_sync_service(None, collaboration)

    assert resolved is None
