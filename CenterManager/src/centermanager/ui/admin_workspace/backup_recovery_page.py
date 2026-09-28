from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QInputDialog,
)

from centermanager.core.current_user import get_current_user
from centermanager.ui.admin_workspace.access import can_write, notify


class BackupRecoveryPage(QWidget):
    def __init__(
        self,
        service,
        permission_service,
        collaboration_manager,
        notification_service,
        parent=None,
    ):
        super().__init__(parent)
        self._service = service
        self._ps = permission_service
        self._cm = collaboration_manager
        self._ns = notification_service
        self._rows = []
        self._setup()
        self.refresh()

    def _setup(self):
        layout = QVBoxLayout(self)
        head = QHBoxLayout()
        head.addWidget(QLabel("<h2>🗄️ Backup & Recovery</h2>"))
        head.addStretch()
        self.create_btn = QPushButton("➕ Create Backup")
        self.create_btn.clicked.connect(self.create_backup)
        head.addWidget(self.create_btn)
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.refresh)
        head.addWidget(self.refresh_btn)
        layout.addLayout(head)

        self.info = QLabel(
            "Restoring replaces the runtime database and metadata. "
            "A safety backup is created automatically after authorization succeeds."
        )
        self.info.setWordWrap(True)
        layout.addWidget(self.info)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Created", "Label", "Location", "Status"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self._update_actions)
        layout.addWidget(self.table, 1)

        foot = QHBoxLayout()
        self.restore_btn = QPushButton("↩ Restore Selected Backup")
        self.restore_btn.clicked.connect(self.restore_selected)
        foot.addWidget(self.restore_btn)
        foot.addStretch()
        layout.addLayout(foot)

    def set_write_enabled(self, enabled):
        self._update_actions()

    def _update_actions(self):
        write = can_write(self._cm)
        self.create_btn.setEnabled(write and self._ps.has_permission("backup.create"))
        actor = get_current_user()
        admin = bool(actor is not None and getattr(actor, "is_admin", False))
        self.restore_btn.setEnabled(
            write and admin and bool(self.table.selectionModel().selectedRows())
        )

    def refresh(self):
        self._rows = self._service.list_backups()
        self.table.setRowCount(len(self._rows))
        for row, backup in enumerate(self._rows):
            self.table.setItem(
                row,
                0,
                QTableWidgetItem(
                    str(backup.get("created_at") or backup.get("timestamp", ""))
                ),
            )
            self.table.setItem(row, 1, QTableWidgetItem(str(backup.get("label", ""))))
            self.table.setItem(row, 2, QTableWidgetItem(str(backup.get("path", ""))))
            status = backup.get("status") or "available"
            self.table.setItem(row, 3, QTableWidgetItem(str(status).title()))
        self._update_actions()

    def create_backup(self):
        if not can_write(self._cm):
            return notify(self._ns, "WRITE mode is required.", "warning")
        result = self._service.create_backup("manual")
        if result.success:
            notify(self._ns, f"Backup created: {result.backup_path}", "success")
            self.refresh()
        else:
            notify(self._ns, f"Backup failed: {result.error}", "error")

    def restore_selected(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        if not can_write(self._cm):
            return notify(self._ns, "WRITE mode is required.", "warning")

        backup = self._rows[rows[0].row()]
        backup_path = backup["path"]
        expected = self._service.confirmation_phrase(backup_path)

        reason, ok = QInputDialog.getText(
            self,
            "Restore Backup",
            "Reason for restoring this backup:",
        )
        if not ok:
            return
        if not str(reason).strip():
            return notify(self._ns, "A restore reason is required.", "warning")

        confirmation, ok = QInputDialog.getText(
            self,
            "Confirm Destructive Restore",
            f'Type exactly "{expected}" to continue:',
        )
        if not ok:
            return

        message = QMessageBox(self)
        message.setIcon(QMessageBox.Icon.Warning)
        message.setWindowTitle("Restore Backup")
        message.setText(
            "Restore this backup? Current runtime database and metadata will be replaced."
        )
        message.setInformativeText(
            "A safety backup will be created first. Restart the application after a "
            "successful restore to ensure all database sessions are refreshed."
        )
        message.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        if message.exec() != QMessageBox.StandardButton.Yes:
            return

        try:
            result = self._service.restore_backup(
                backup_path,
                reason=reason,
                confirmation=confirmation,
            )
        except Exception as exc:
            return notify(self._ns, f"Restore rejected: {exc}", "error")

        if result.success:
            notify(
                self._ns,
                "Backup restored successfully. Please restart the application.",
                "success",
            )
            self.refresh()
        else:
            notify(self._ns, f"Restore failed: {result.error}", "error")
