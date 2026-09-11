# -*- coding: utf-8 -*-
"""Validation results page."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWizardPage, QVBoxLayout, QLabel, QTextEdit,
    QPushButton, QHBoxLayout
)

from centermanager.platform.deployment import RuntimeValidator


class ValidationPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Deployment Validation")
        self.setSubTitle("Verifying that everything is ready")

        layout = QVBoxLayout(self)

        self.status_label = QLabel()
        self.status_label.setStyleSheet("font-weight: bold; font-size: 16px;")
        layout.addWidget(self.status_label)

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(200)
        layout.addWidget(self.details_text)

        self.revalidate_btn = QPushButton("Re-validate")
        self.revalidate_btn.clicked.connect(self._validate)
        layout.addWidget(self.revalidate_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()

        self._validator = RuntimeValidator()
        self._validated = False

    def initializePage(self):
        self._validate()

    def _validate(self):
        result = self._validator.validate_all()
        self._validated = True

        if result.severity.value == "HEALTHY":
            self.status_label.setText("✅ " + result.message)
            self.status_label.setStyleSheet("color: #2e7d32; font-weight: bold; font-size: 16px;")
        elif result.severity.value == "WARNING":
            self.status_label.setText("⚠️ " + result.message)
            self.status_label.setStyleSheet("color: #ed6c02; font-weight: bold; font-size: 16px;")
        else:
            self.status_label.setText("❌ " + result.message)
            self.status_label.setStyleSheet("color: #d32f2f; font-weight: bold; font-size: 16px;")

        self.details_text.clear()
        if result.details:
            self.details_text.append("Details:\n")
            for line in result.details:
                self.details_text.append("• " + line)
        else:
            self.details_text.append("All checks passed.")

        self.completeChanged.emit()

    def set_status(self, success: bool, message: str):
        if success:
            self.status_label.setText("✅ " + message)
            self.status_label.setStyleSheet("color: #2e7d32; font-weight: bold; font-size: 16px;")
        else:
            self.status_label.setText("❌ " + message)
            self.status_label.setStyleSheet("color: #d32f2f; font-weight: bold; font-size: 16px;")
        self.details_text.clear()
        self.details_text.append("Please check configuration and try again.")
        self.completeChanged.emit()

    def isComplete(self) -> bool:
        return self._validated and self._validator.is_healthy()