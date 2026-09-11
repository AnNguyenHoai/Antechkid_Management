# -*- coding: utf-8 -*-
"""Authentication page for Git token."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWizardPage, QVBoxLayout, QFormLayout, QLineEdit,
    QLabel, QCheckBox
)


class AuthPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Authentication")
        self.setSubTitle("Provide your Git personal access token")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.token_edit = QLineEdit()
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_edit.setPlaceholderText("ghp_xxxxxxxxxxxxxxxxxxxx")
        self.token_edit.textChanged.connect(self.completeChanged)
        form.addRow("Personal Access Token:", self.token_edit)

        self.remember_check = QCheckBox("Remember token (stored locally)")
        self.remember_check.setChecked(True)
        form.addRow("", self.remember_check)

        layout.addLayout(form)

        help_label = QLabel(
            "Token is required to clone the repository.\n"
            "It will be stored in deployment configuration."
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("font-size: 11px; color: #666;")
        layout.addWidget(help_label)

        layout.addStretch()

    def get_token(self) -> str:
        return self.token_edit.text().strip()

    def should_remember(self) -> bool:
        return self.remember_check.isChecked()

    def isComplete(self) -> bool:
        return bool(self.get_token())