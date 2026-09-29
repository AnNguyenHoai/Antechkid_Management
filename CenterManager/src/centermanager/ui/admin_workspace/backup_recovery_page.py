from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QInputDialog,
    QLineEdit,
)

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
            "Restore is a destructive maintenance recovery operation. It is available "
            "only from READ mode for an integrity-validated backup and requires a "
            "reason plus typed confirmation. Recovery publishes the restored runtime "
            "authoritatively before success is reported."
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
        permitted = self._ps.has_permission("backup.restore")

        # SEC06-13R-C2: recovery is deliberately separate from the normal
        # Start Editing -> Finish Editing transaction. It may enter only from
        # READ mode, with an integrity-valid backup and explicit capability.
        self.restore_btn.setEnabled(
            bool(not write and restore_eligible and permitted)
        )
        if not backup:
            self.restore_btn.setToolTip("Select a validated backup to restore.")
        elif not restore_eligible:
            self.restore_btn.setToolTip(
                "Restore is disabled because this backup did not pass integrity validation."
            )
        elif write:
            self.restore_btn.setToolTip(
                "Finish or cancel the current editing session before starting recovery."
            )
        elif not permitted:
            self.restore_btn.setToolTip("Backup restore capability is required.")
        else:
            self.restore_btn.setToolTip(
                "Restore this backup using dedicated recovery authority."
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

    def _collect_restore_intent(self, backup_path):
        reason, ok = QInputDialog.getMultiLineText(
            self,
            "Restore backup",
            "Reason for this destructive recovery operation:",
        )
        reason = str(reason or "").strip()
        if not ok:
            return None
        if not reason:
            notify(self._ns, "Restore reason is required.", "warning")
            return None

        expected = self._service.confirmation_phrase(backup_path)
        confirmation, ok = QInputDialog.getText(
            self,
            "Confirm restore",
            f'Type "{expected}" to confirm:',
            QLineEdit.EchoMode.Normal,
        )
        if not ok:
            return None
        return reason, str(confirmation or "")

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
        if can_write(self._cm):
            return notify(
                self._ns,
                "Finish or cancel the current editing session before starting recovery.",
                "warning",
            )
        if not self._ps.has_permission("backup.restore"):
            return notify(self._ns, "Backup restore capability is required.", "error")

        backup_path = backup.get("path")
        if not backup_path:
            return notify(self._ns, "Restore rejected: backup path is missing.", "error")

        intent = self._collect_restore_intent(backup_path)
        if intent is None:
            return
        reason, confirmation = intent

        try:
            result = self._service.restore_backup(
                backup_path,
                reason=reason,
                confirmation=confirmation,
            )
        except Exception as exc:
            # Service-side authorization/validation is authoritative. Keep this
            # UI path fail-closed and never route recovery through Finish Editing.
            return notify(self._ns, f"Restore rejected: {exc}", "error")

        if result.success:
            notify(
                self._ns,
                "Backup restored and authoritative recovery publish completed.",
                "success",
            )
            self.refresh()
            return

        error = result.error or "unknown recovery error"
        if "authoritative recovery publish" in str(error).lower():
            notify(
                self._ns,
                f"Recovery incomplete: {error}",
                "error",
            )
        else:
            notify(self._ns, f"Restore failed: {error}", "error")
