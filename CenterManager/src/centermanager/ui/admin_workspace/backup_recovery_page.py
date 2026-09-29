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
            "Restore is a maintenance recovery operation and cannot run inside a normal "
            "editing session. Dedicated recovery authority is being introduced before "
            "Restore is re-enabled."
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

    @staticmethod
    def _is_restore_eligible(backup):
        """Return True only for backups that passed integrity validation."""
        return str(backup.get("status") or "").strip().lower() == "valid"

    def _selected_backup(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        if row < 0 or row >= len(self._rows):
            return None
        return self._rows[row]

    def _update_actions(self):
        write = can_write(self._cm)
        self.create_btn.setEnabled(write and self._ps.has_permission("backup.create"))
        backup = self._selected_backup()
        restore_eligible = bool(backup and self._is_restore_eligible(backup))

        # SEC06-13R-A: fail closed. Restore must not run inside the normal
        # Start Editing -> Finish Editing lifecycle. Phase B will enable the
        # action from READ only after dedicated recovery authority exists.
        self.restore_btn.setEnabled(False)
        if backup and not restore_eligible:
            self.restore_btn.setToolTip(
                "Restore is disabled because this backup did not pass integrity validation."
            )
        elif write:
            self.restore_btn.setToolTip(
                "Finish or cancel the current editing session before starting recovery."
            )
        else:
            self.restore_btn.setToolTip(
                "Restore is temporarily disabled until dedicated recovery authority is available."
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
        backup = self._selected_backup()
        if backup is None:
            return
        if not self._is_restore_eligible(backup):
            return notify(
                self._ns,
                "Restore rejected: selected backup did not pass integrity validation.",
                "error",
            )

        # Defense in depth for programmatic/direct invocation. The button is
        # disabled in Phase A, but this guard prevents the old destructive flow
        # from being entered through a direct slot call.
        if can_write(self._cm):
            return notify(
                self._ns,
                "Finish or cancel the current editing session before starting recovery.",
                "warning",
            )
        return notify(
            self._ns,
            "Restore is temporarily disabled until dedicated recovery authority is available.",
            "warning",
        )
