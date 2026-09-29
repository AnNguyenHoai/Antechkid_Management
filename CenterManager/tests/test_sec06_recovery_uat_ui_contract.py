from types import SimpleNamespace

from PySide6.QtWidgets import QMainWindow, QMessageBox

from centermanager.ui.admin_workspace.backup_recovery_page import BackupRecoveryPage


class _PermissionService:
    def __init__(self, permissions):
        self._permissions = set(permissions)

    def has_permission(self, name):
        return name in self._permissions


class _CollaborationManager:
    def __init__(self, writing=False):
        self.writing = writing

    def is_initialized(self):
        return True

    def is_writing(self):
        return self.writing


class _Notifications:
    def __init__(self, live=True):
        self._listeners = [object()] if live else []
        self.messages = []

    def notify(self, message, severity="info"):
        self.messages.append((message, severity))


class _BackupService:
    def __init__(self):
        self.backups = [
            {
                "created_at": "2026-09-29T00:00:00",
                "label": "manual",
                "path": "C:/uat/Backup/manual_A",
                "status": "valid",
            }
        ]
        self.restore_calls = []
        self.create_calls = []
        self.restore_result = SimpleNamespace(
            success=False,
            error="synthetic restore rejection",
            requires_restart=False,
        )

    def list_backups(self):
        return list(self.backups)

    def create_backup(self, label):
        self.create_calls.append(label)
        return SimpleNamespace(success=True, backup_path="C:/uat/Backup/new", error=None)

    def confirmation_phrase(self, backup_path):
        return "RESTORE manual_A"

    def restore_backup(self, backup_path, *, reason, confirmation):
        self.restore_calls.append((backup_path, reason, confirmation))
        return self.restore_result


def _page(*, writing=False, notification_live=True):
    service = _BackupService()
    permissions = _PermissionService({"backup.create", "backup.restore"})
    collaboration = _CollaborationManager(writing=writing)
    notifications = _Notifications(live=notification_live)
    page = BackupRecoveryPage(service, permissions, collaboration, notifications)
    return page, service, collaboration, notifications


def test_backup_and_restore_actions_are_read_mode_only(qapp):
    page, _, collaboration, _ = _page(writing=False)

    assert page.create_btn.isEnabled() is True
    page.table.selectRow(0)
    qapp.processEvents()
    assert page.restore_btn.isEnabled() is True

    collaboration.writing = True
    page.set_write_enabled(True)
    qapp.processEvents()

    assert page.create_btn.isEnabled() is False
    assert page.restore_btn.isEnabled() is False


def test_restore_without_selection_never_returns_silently(monkeypatch):
    page, _, _, notifications = _page(writing=False, notification_live=False)
    warnings = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args: warnings.append(args[2] if len(args) > 2 else ""),
    )

    page.restore_selected()

    assert warnings
    assert "Select a validated backup" in warnings[0]
    assert notifications.messages == []


def test_recovery_feedback_prefers_main_window_live_notification_service(qapp):
    page, _, _, isolated = _page(writing=False, notification_live=False)
    live = _Notifications(live=True)
    window = QMainWindow()
    window._notification_service = live
    window.setCentralWidget(page)
    qapp.processEvents()

    page._notify("recovery feedback", "warning")

    assert live.messages == [("recovery feedback", "warning")]
    assert isolated.messages == []


def test_restore_selected_calls_service_and_surfaces_failure(monkeypatch, qapp):
    page, service, _, notifications = _page(writing=False, notification_live=True)
    page.table.selectRow(0)
    qapp.processEvents()
    monkeypatch.setattr(
        page,
        "_collect_restore_intent",
        lambda backup_path: ("UAT restore A", "RESTORE manual_A"),
    )
    monkeypatch.setattr(page, "_ensure_recovery_publisher", lambda: None)

    page.restore_selected()

    assert service.restore_calls == [
        ("C:/uat/Backup/manual_A", "UAT restore A", "RESTORE manual_A")
    ]
    assert notifications.messages[-1] == (
        "Restore failed: synthetic restore rejection",
        "error",
    )


def test_create_backup_rejects_write_mode_with_visible_feedback():
    page, service, _, notifications = _page(writing=True, notification_live=True)

    page.create_backup()

    assert service.create_calls == []
    assert notifications.messages[-1][1] == "warning"
    assert "Finish Editing before creating a backup" in notifications.messages[-1][0]
