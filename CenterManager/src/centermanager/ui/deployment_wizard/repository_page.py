# -*- coding: utf-8 -*-
"""Repository configuration page."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWizardPage, QVBoxLayout, QFormLayout, QLineEdit,
    QLabel, QFileDialog, QPushButton, QHBoxLayout
)
from pathlib import Path

from centermanager.core.paths import get_paths


class RepositoryPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Repository Configuration")
        self.setSubTitle("Enter the URL and location of the data repository")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Repository URL
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://github.com/org/repo.git")
        self.url_edit.textChanged.connect(self.completeChanged)
        form.addRow("Repository URL:", self.url_edit)

        # Branch
        self.branch_edit = QLineEdit()
        self.branch_edit.setPlaceholderText("main")
        self.branch_edit.setText("main")
        self.branch_edit.textChanged.connect(self.completeChanged)
        form.addRow("Branch:", self.branch_edit)

        # Local path
        path_layout = QHBoxLayout()
        default_path = get_paths().runtime_root / "repository"
        self.path_edit = QLineEdit()
        self.path_edit.setText(str(default_path))
        self.path_edit.setReadOnly(True)
        self.path_edit.textChanged.connect(self.completeChanged)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_path)
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(browse_btn)
        form.addRow("Local Repository Path:", path_layout)

        layout.addLayout(form)
        layout.addStretch()

        # Help text
        help_label = QLabel(
            "The repository should contain the 'database', 'metadata', and 'reports' folders.\n"
            "It is typically created by your system administrator."
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("font-size: 11px; color: #666;")
        layout.addWidget(help_label)

    def _browse_path(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Local Repository Folder",
            str(self.path_edit.text())
        )
        if dir_path:
            self.path_edit.setText(dir_path)

    def get_repository_url(self) -> str:
        return self.url_edit.text().strip()

    def get_branch(self) -> str:
        return self.branch_edit.text().strip() or "main"

    def get_local_path(self) -> str:
        return self.path_edit.text().strip()

    def isComplete(self) -> bool:
        return bool(self.get_repository_url())