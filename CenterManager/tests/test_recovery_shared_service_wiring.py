from types import SimpleNamespace

import centermanager.ui.main_window as main_window_module


class _SignalStub:
    def __init__(self):
        self.connected = []

    def connect(self, callback):
        self.connected.append(callback)


class _StackStub:
    def __init__(self):
        self.widgets = []

    def addWidget(self, widget):
        self.widgets.append(widget)


def test_main_window_injects_shared_recovery_services(monkeypatch):
    """Recovery must reuse the application's live notification/sync services."""
    captured = {}

    class _AdminWorkspaceShellStub:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.go_home = _SignalStub()

    monkeypatch.setattr(
        main_window_module,
        "AdminWorkspaceShell",
        _AdminWorkspaceShellStub,
    )

    notification_service = object()
    runtime_sync_service = object()
    window = SimpleNamespace(
        _permission_service=object(),
        _git_config_service=object(),
        _platform_context=object(),
        _collaboration_manager=object(),
        _notification_service=notification_service,
        _sync_service=runtime_sync_service,
        _go_home=lambda: None,
        central_stack=_StackStub(),
    )

    main_window_module.MainWindow._setup_admin_workspace(window)

    assert captured["notification_service"] is notification_service
    assert captured["runtime_sync_service"] is runtime_sync_service
    assert window.central_stack.widgets == [window.admin_workspace]
