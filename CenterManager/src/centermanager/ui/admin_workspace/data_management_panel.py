# -*- coding: utf-8 -*-
"""Admin System Operations panel for previewing and resetting workspace data."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from centermanager.services.admin_data_reset import AdminDataResetError


class DataManagementPanel(QFrame):
    data_reset_completed = Signal(str)

    _SCOPES = (
        ("Student data", "student"),
        ("Class data", "class"),
        ("Teacher data", "teacher"),
        ("Employee data", "employee"),
        ("Finance data", "finance"),
        ("Operational data", "operational"),
        ("All business data", "all_business"),
    )

    def __init__(self, reset_service, notification_service=None, parent=None):
        super().__init__(parent)
        self._service = reset_service
        self._notification_service = notification_service
        self._last_preview = None
        self._write_enabled = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        title = QLabel("🧹 Data Management")
        title.setStyleSheet("font-size:16px;font-weight:700;")
        layout.addWidget(title)
        description = QLabel(
            "Preview and reset test/business data by workspace. A safety backup is "
            "created automatically before deletion. Auth/config/schema data are preserved."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        form = QFormLayout()
        self.scope_combo = QComboBox()
        for label, value in self._SCOPES:
            self.scope_combo.addItem(label, value)
        self.scope_combo.currentIndexChanged.connect(self._invalidate_preview)
        form.addRow("Workspace scope", self.scope_combo)

        self.include_finance = QCheckBox("Include related finance data")
        self.include_finance.stateChanged.connect(self._invalidate_preview)
        form.addRow("Finance", self.include_finance)

        self.reason = QLineEdit()
        self.reason.setPlaceholderText("Required reason, e.g. Reset before regression test")
        form.addRow("Reason", self.reason)

        self.confirmation = QLineEdit()
        self.confirmation.setPlaceholderText("Preview first to see the required phrase")
        form.addRow("Typed confirmation", self.confirmation)
        layout.addLayout(form)

        actions = QHBoxLayout()
        self.preview_button = QPushButton("Preview Reset")
        self.preview_button.clicked.connect(self.preview)
        actions.addWidget(self.preview_button)
        self.reset_button = QPushButton("Reset Data")
        self.reset_button.clicked.connect(self.reset)
        self.reset_button.setEnabled(False)
        actions.addWidget(self.reset_button)
        actions.addStretch()
        layout.addLayout(actions)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(220)
        self.preview_text.setPlaceholderText("Preview will show affected rows and blockers.")
        layout.addWidget(self.preview_text)

    def _scope(self) -> str:
        return str(self.scope_combo.currentData())

    def _invalidate_preview(self, *_args) -> None:
        self._last_preview = None
        self.preview_text.clear()
        self._refresh_reset_enabled()

    def _notify(self, message: str, severity: str = "info") -> None:
        if self._notification_service is not None:
            self._notification_service.notify(message, severity)

    def _refresh_reset_enabled(self) -> None:
        self.reset_button.setEnabled(
            bool(self._write_enabled and self._last_preview and self._last_preview.can_reset)
        )

    def set_write_enabled(self, enabled: bool) -> None:
        self._write_enabled = bool(enabled)
        self._refresh_reset_enabled()

    def preview(self) -> None:
        try:
            preview = self._service.preview(
                self._scope(), include_finance=self.include_finance.isChecked()
            )
        except AdminDataResetError as exc:
            self._last_preview = None
            self.preview_text.setPlainText(str(exc))
            self._notify(str(exc), "warning")
            self._refresh_reset_enabled()
            return

        self._last_preview = preview
        lines = [
            f"Scope: {preview.scope}",
            f"Rows selected: {preview.total_rows}",
            "",
            "Affected tables:",
        ]
        populated = [(name, count) for name, count in preview.counts.items() if count]
        if populated:
            lines.extend(f"  - {name}: {count}" for name, count in populated)
        else:
            lines.append("  - No rows currently stored in this scope.")

        if preview.finance_counts:
            lines.extend(("", "Finance rows currently present:"))
            lines.extend(
                f"  - {name}: {count}" for name, count in preview.finance_counts.items()
            )

        if preview.blockers:
            lines.extend(("", "BLOCKED — retained tables still reference this scope:"))
            lines.extend(
                f"  - {name}: {count}" for name, count in preview.blockers.items()
            )
            lines.append(
                "Enable related finance data when applicable, or reset the dependent scope first."
            )
        else:
            lines.extend(("", "Dependency check: OK"))
            lines.append(f'Type exactly: {preview.confirmation_phrase}')

        self.preview_text.setPlainText("\n".join(lines))
        self.confirmation.setPlaceholderText(preview.confirmation_phrase)
        self._refresh_reset_enabled()

    def reset(self) -> None:
        if self._last_preview is None:
            self.preview()
            return
        if not self._write_enabled:
            self._notify("Request WRITE mode before resetting data.", "warning")
            return

        answer = QMessageBox.warning(
            self,
            "Confirm destructive data reset",
            "A safety backup will be created first. The selected business data will then "
            "be permanently deleted from the active database.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            result = self._service.reset(
                self._scope(),
                include_finance=self.include_finance.isChecked(),
                reason=self.reason.text(),
                confirmation=self.confirmation.text(),
            )
        except AdminDataResetError as exc:
            self._notify(str(exc), "error")
            QMessageBox.critical(self, "Data reset failed", str(exc))
            return

        QMessageBox.information(
            self,
            "Data reset completed",
            f"Deleted {result.deleted_rows} rows.\nSafety backup: {result.backup_path}",
        )
        self._notify(f"{result.scope} data reset completed.", "success")
        self.data_reset_completed.emit(result.scope)
        self.confirmation.clear()
        self.preview()
