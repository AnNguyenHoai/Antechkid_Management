# -*- coding: utf-8 -*-
"""
GitConfigDialog - First-run dialog for Git configuration.
"""

import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QTextEdit, QPushButton, QMessageBox,
    QProgressBar, QWidget
)

from centermanager.services.git_config_service import GitConfigService, GitConfigValidationError

logger = logging.getLogger(__name__)


class GitConfigDialog(QDialog):
    """First-run dialog for Git configuration."""

    config_saved = Signal()

    def __init__(
        self,
        git_config_service: GitConfigService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._git_config_service = git_config_service

        self.setWindowTitle("Git Configuration")
        self.setMinimumSize(600, 400)
        self.setModal(True)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Header
        header = QLabel("🔐 Git Configuration")
        header.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(header)

        desc = QLabel(
            "Please paste the encrypted Git configuration bundle provided by your administrator.\n"
            "The bundle contains repository URL, username, and access token."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; font-size: 13px;")
        layout.addWidget(desc)

        # Bundle input
        form = QFormLayout()
        form.setSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.bundle_edit = QTextEdit()
        self.bundle_edit.setPlaceholderText("Paste encrypted configuration bundle (ENC:v1:...)")
        self.bundle_edit.setMaximumHeight(100)
        self.bundle_edit.textChanged.connect(self._on_bundle_changed)
        form.addRow("Encrypted Configuration:", self.bundle_edit)

        layout.addLayout(form)

        # Status message
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("font-size: 13px;")
        layout.addWidget(self.status_label)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.test_btn = QPushButton("🔍 Test Connection")
        self.test_btn.setFixedHeight(34)
        btn_layout.addWidget(self.test_btn)

        btn_layout.addStretch()

        self.save_btn = QPushButton("💾 Save")
        self.save_btn.setFixedHeight(34)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background: #1976d2;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #1565c0;
            }
            QPushButton:disabled {
                background: #b0b0b0;
            }
        """)
        self.save_btn.setEnabled(False)
        btn_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedHeight(34)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()

    def _connect_signals(self) -> None:
        self.test_btn.clicked.connect(self._test_connection)
        self.save_btn.clicked.connect(self._save_config)
        self.cancel_btn.clicked.connect(self.reject)
        self.bundle_edit.textChanged.connect(self._on_bundle_changed)

    def _on_bundle_changed(self) -> None:
        bundle = self.bundle_edit.toPlainText().strip()
        has_text = bool(bundle)
        self.save_btn.setEnabled(has_text)
        self.status_label.clear()

    def _test_connection(self) -> None:
        bundle = self.bundle_edit.toPlainText().strip()
        if not bundle:
            self.status_label.setText("⚠️ Please paste an encrypted configuration bundle.")
            self.status_label.setStyleSheet("color: #d32f2f; font-size: 13px;")
            return

        self.progress.setVisible(True)
        self.test_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.status_label.setText("⏳ Testing connection...")
        self.status_label.setStyleSheet("color: #1976d2; font-size: 13px;")

        try:
            result = self._git_config_service.validate_bundle(bundle)
            if result.success:
                self.status_label.setText("✅ Connection successful!")
                self.status_label.setStyleSheet("color: #2e7d32; font-size: 13px;")
                self.save_btn.setEnabled(True)
            else:
                self.status_label.setText(f"❌ Connection failed: {result.message}")
                self.status_label.setStyleSheet("color: #d32f2f; font-size: 13px;")
                self.save_btn.setEnabled(False)
        except GitConfigValidationError as e:
            self.status_label.setText(f"❌ Invalid bundle: {str(e)}")
            self.status_label.setStyleSheet("color: #d32f2f; font-size: 13px;")
            self.save_btn.setEnabled(False)
        except Exception as e:
            logger.exception("Test connection failed")
            self.status_label.setText(f"❌ Error: {str(e)}")
            self.status_label.setStyleSheet("color: #d32f2f; font-size: 13px;")
            self.save_btn.setEnabled(False)
        finally:
            self.progress.setVisible(False)
            self.test_btn.setEnabled(True)

    def _save_config(self) -> None:
        bundle = self.bundle_edit.toPlainText().strip()
        if not bundle:
            return

        try:
            self._git_config_service.save_encrypted_bundle(bundle)
            self.status_label.setText("✅ Configuration saved successfully!")
            self.status_label.setStyleSheet("color: #2e7d32; font-size: 13px;")
            self.config_saved.emit()
            self.accept()
        except GitConfigValidationError as e:
            QMessageBox.warning(self, "Validation Error", str(e))
        except Exception as e:
            logger.exception("Failed to save Git configuration")
            QMessageBox.critical(self, "Error", f"Failed to save configuration: {str(e)}")