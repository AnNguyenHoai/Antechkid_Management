from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QInputDialog,
    QLineEdit,
    QMessageBox,
)

from centermanager.platform.backup.recovery_publisher import AuthoritativeRecoveryPublisher
from centermanager.ui.admin_workspace.access import can_write, notify


RECOVERY_RESTART_EXIT_CODE = 86


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
            "Create Backup and Restore are maintenance operations that run only from "
            "READ mode. Finish Editing first so backups represent a committed, stable "
            "generation. Restore additionally requires an integrity-validated backup, "
            "a reason, typed confirmation, exclusive recovery authority and an "
            "authoritative publish before success is reported."
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

    def _notification_target(self):
        """Use the application notification service once this page is parented.

        Older AdminWorkspace construction paths created an isolated
        NotificationService with no listeners. Recovery feedback is safety
        critical, so prefer MainWindow's live service and only use the injected
        fallback when no application-level service is available.
        """
        try:
            root = self.window()
            application_service = getattr(root, "_notification_service", None)
            if application_service is not None:
                return application_service
        except Exception:
            pass
        return self._ns

    def _notify(self, message: str, severity: str = "info") -> None:
        target = self._notification_target()
        listeners = getattr(target, "_listeners", None) if target is not None else None
        if target is not None and (listeners is None or bool(listeners)):
            notify(target, message, severity)
            return

        # Fail visibly if the notification service is absent or isolated. Silent
        # recovery rejection is unsafe because the operator cannot tell whether
        # destructive mutation happened.
        if severity == "error":
            QMessageBox.critical(self, "Backup & Recovery", message)
        elif severity == "warning":
            QMessageBox.warning(self, "Backup & Recovery", message)
        else:
            QMessageBox.information(self, "Backup & Recovery", message)

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
        create_permitted = self._ps.has_permission("backup.create")
        self.create_btn.setEnabled(bool(not write and create_permitted))
        if write:
            self.create_btn.setToolTip(
                "Finish Editing before creating a backup so it captures a committed generation."
            )
        elif not create_permitted:
            self.create_btn.setToolTip("Backup create capability is required.")
        else:
            self.create_btn.setToolTip("Create a backup of the current committed runtime state.")

        backup = self._selected_backup()
        restore_eligible = bool(backup and self._is_restore_eligible(backup))
        permitted = self._ps.has_permission("backup.restore")

        self.restore_btn.setEnabled(bool(not write and restore_eligible and permitted))
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
        selected = self._selected_backup()
        selected_path = str(selected.get("path")) if selected and selected.get("path") else None

        self._rows = self._service.list_backups()
        self.table.setRowCount(len(self._rows))
        selected_row = None
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
            if selected_path and str(backup.get("path")) == selected_path:
                selected_row = row
        if selected_row is not None:
            self.table.selectRow(selected_row)
        self._update_actions()

    def create_backup(self):
        if can_write(self._cm):
            return self._notify(
                "Finish Editing before creating a backup. Backups must capture a committed READ-mode generation.",
                "warning",
            )
        if not self._ps.has_permission("backup.create"):
            return self._notify("Backup create capability is required.", "error")

        result = self._service.create_backup("manual")
        if result.success:
            self._notify(f"Backup created: {result.backup_path}", "success")
            self.refresh()
        else:
            self._notify(f"Backup failed: {result.error}", "error")

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
            self._notify("Restore reason is required.", "warning")
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

    def _ensure_recovery_publisher(self):
        """Bind the already-running sync service without creating a second pipeline."""
        if getattr(self._service, "_recovery_publisher", None) is not None:
            return
        root = self.window()
        runtime_sync = getattr(root, "_sync_service", None)
        if runtime_sync is not None:
            self._service._recovery_publisher = AuthoritativeRecoveryPublisher(runtime_sync)

    def _terminate_for_recovery_restart(self, *, success: bool, error: str = ""):
        """Fence the stale process immediately after any successful local DB replacement.

        Recovery deliberately does not hot-reload the restored database. RuntimeSync and
        write handoff stay quiesced until a fresh process performs normal authoritative
        startup synchronization. Disable the live window before requesting application
        exit so no Start Editing/write action can race the queued Qt shutdown.
        """
        if success:
            text = (
                "Recovery was published successfully. CenterManager must now close "
                "so the restored authoritative generation can be loaded by the normal "
                "startup synchronization. Please reopen CenterManager."
            )
            QMessageBox.information(self, "Recovery complete - restart required", text)
        else:
            text = (
                "The local database was restored, but authoritative publication did not "
                "complete. This process is no longer safe to use and must close now. "
                "On the next start, the authoritative remote database will win.\n\n"
                f"Details: {error}"
            )
            QMessageBox.critical(self, "Recovery incomplete - restart required", text)

        root = self.window()
        try:
            root.setEnabled(False)
        except Exception:
            pass

        app = QApplication.instance()
        if app is not None:
            # exit() is processed by Qt's event loop. The window fence above closes the
            # short interval in which the operator could otherwise click Start Editing
            # while the post-restore write-handoff guard intentionally remains closed.
            app.exit(RECOVERY_RESTART_EXIT_CODE)

    def restore_selected(self):
        backup = self._selected_backup()
        if backup is None:
            return self._notify("Select a validated backup to restore.", "warning")
        if not self._is_restore_eligible(backup):
            return self._notify(
                "Restore rejected: selected backup did not pass integrity validation.",
                "error",
            )
        if can_write(self._cm):
            return self._notify(
                "Finish or cancel the current editing session before starting recovery.",
                "warning",
            )
        if not self._ps.has_permission("backup.restore"):
            return self._notify("Backup restore capability is required.", "error")

        backup_path = backup.get("path")
        if not backup_path:
            return self._notify("Restore rejected: backup path is missing.", "error")

        intent = self._collect_restore_intent(backup_path)
        if intent is None:
            return
        reason, confirmation = intent
        self._ensure_recovery_publisher()

        try:
            result = self._service.restore_backup(
                backup_path,
                reason=reason,
                confirmation=confirmation,
            )
        except Exception as exc:
            return self._notify(f"Restore rejected: {exc}", "error")

        restart_required = bool(getattr(result, "requires_restart", False))
        if result.success:
            self._notify(
                "Backup restored and authoritative recovery publish completed.",
                "success",
            )
            if restart_required:
                self._terminate_for_recovery_restart(success=True)
            return

        error = result.error or "unknown recovery error"
        if restart_required:
            self._notify(f"Recovery incomplete: {error}", "error")
            self._terminate_for_recovery_restart(success=False, error=str(error))
        elif "authoritative recovery publish" in str(error).lower():
            self._notify(f"Recovery incomplete: {error}", "error")
        else:
            self._notify(f"Restore failed: {error}", "error")
