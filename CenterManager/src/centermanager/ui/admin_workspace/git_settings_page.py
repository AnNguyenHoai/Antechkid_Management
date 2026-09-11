# -*- coding: utf-8 -*-
"""
GitSettingsPage - Git configuration page for Admin Workspace.
"""

import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox,
    QFrame, QScrollArea, QSizePolicy, QTextEdit,
    QProgressBar
)

from centermanager.services.git_config_service import GitConfigService, GitConfigValidationError
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.notification import NotificationService
from centermanager.ui.admin_workspace.access import can_write, notify

logger = logging.getLogger(__name__)


class GitSettingsPage(QWidget):
    """Git configuration page with encrypted bundle support."""

    config_changed = Signal()

    def __init__(
        self,
        git_config_service: GitConfigService,
        collaboration_manager: CollaborationManager,
        notification_service: Optional[NotificationService] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._git_config_service = git_config_service
        self._collaboration_manager = collaboration_manager
        self._notification_service = notification_service
        self._write_enabled = can_write(self._collaboration_manager)
        self._bundle_valid = False

        self._setup_ui()
        self._load_status()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        header = QLabel("Git Configuration")
        header.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(header)

        # Status section
        status_frame = QFrame()
        status_frame.setFrameShape(QFrame.Shape.Box)
        status_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background: #fafafa;
                padding: 12px;
            }
        """)
        status_layout = QVBoxLayout(status_frame)

        self.status_label = QLabel("Status: Checking...")
        self.status_label.setStyleSheet("font-size: 14px;")
        status_layout.addWidget(self.status_label)

        self.repo_label = QLabel("Repository: -")
        self.repo_label.setStyleSheet("font-size: 13px; color: #666;")
        status_layout.addWidget(self.repo_label)

        self.user_label = QLabel("Username: -")
        self.user_label.setStyleSheet("font-size: 13px; color: #666;")
        status_layout.addWidget(self.user_label)

        layout.addWidget(status_frame)

        # Encrypted bundle input
        form = QFormLayout()
        form.setSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.bundle_edit = QTextEdit()
        self.bundle_edit.setPlaceholderText("Paste encrypted configuration bundle (ENC:v1:...)")
        self.bundle_edit.setMaximumHeight(80)
        self.bundle_edit.textChanged.connect(self._on_bundle_changed)
        form.addRow("Encrypted Configuration:", self.bundle_edit)

        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.test_btn = QPushButton("🔍 Test Connection")
        self.test_btn.setFixedHeight(34)
        self.test_btn.clicked.connect(self._test_connection)
        btn_layout.addWidget(self.test_btn)

        self.save_btn = QPushButton("💾 Save Configuration")
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
        self.save_btn.clicked.connect(self._save_config)
        btn_layout.addWidget(self.save_btn)

        self.change_btn = QPushButton("🔄 Change Configuration")
        self.change_btn.setFixedHeight(34)
        self.change_btn.clicked.connect(self._enable_edit)
        btn_layout.addWidget(self.change_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Progress bar for test
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # Status message
        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet("color: #666; font-size: 13px;")
        layout.addWidget(self.message_label)

        layout.addStretch()

        # Initial state
        self._update_buttons()
        self._enable_edit(False)

    def _load_status(self) -> None:
        """Load and display current config status."""
        if self._git_config_service is not None and self._git_config_service.has_config():
            config = self._git_config_service.get_config()
            if config:
                self.status_label.setText("✅ Configured")
                self.status_label.setStyleSheet("color: #2e7d32; font-size: 14px; font-weight: bold;")
                self.repo_label.setText(f"Repository: {config.repository_url}")
                self.user_label.setText(f"Username: {config.username}")
                self.change_btn.setVisible(True)
                self.bundle_edit.setReadOnly(True)
                self.bundle_edit.setStyleSheet("background: #f5f5f5;")
            else:
                self._show_not_configured()
        else:
            self._show_not_configured()

    def _show_not_configured(self) -> None:
        self.status_label.setText("❌ Not configured")
        self.status_label.setStyleSheet("color: #d32f2f; font-size: 14px; font-weight: bold;")
        self.repo_label.setText("Repository: -")
        self.user_label.setText("Username: -")
        self.change_btn.setVisible(False)
        self.bundle_edit.setReadOnly(False)
        self.bundle_edit.setStyleSheet("")

    def _enable_edit(self, enabled: bool = True) -> None:
        """Enable editing of bundle field."""
        if enabled:
            self.bundle_edit.setReadOnly(False)
            self.bundle_edit.setStyleSheet("")
            self.bundle_edit.clear()
            self.change_btn.setVisible(False)
            self.save_btn.setEnabled(False)
            self.test_btn.setEnabled(False)
            self.message_label.clear()
        else:
            self._load_status()

    def _on_bundle_changed(self) -> None:
        """Update button state when bundle changes."""
        bundle = self.bundle_edit.toPlainText().strip()
        self._bundle_valid = False
        self._update_buttons()

    def _update_buttons(self) -> None:
        """Update button states without assuming Collaboration is initialized."""
        self._write_enabled = can_write(self._collaboration_manager)
        has_text = bool(self.bundle_edit.toPlainText().strip())
        editable = not self.bundle_edit.isReadOnly()

        self.change_btn.setEnabled(
            self._write_enabled and self._git_config_service is not None
        )
        self.test_btn.setEnabled(
            self._write_enabled and editable and has_text
            and self._git_config_service is not None
        )
        self.save_btn.setEnabled(
            self._write_enabled and editable and has_text and self._bundle_valid
            and self._git_config_service is not None
        )

    def _test_connection(self) -> None:
        """Test the encrypted configuration connection."""
        bundle = self.bundle_edit.toPlainText().strip()
        if not bundle:
            QMessageBox.warning(self, "Error", "Please paste an encrypted configuration bundle.")
            return

        self.progress.setVisible(True)
        self.test_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.message_label.setText("Testing connection...")

        try:
            result = self._git_config_service.validate_bundle(bundle)
            if result.success:
                self.message_label.setText("✅ Connection successful!")
                self.message_label.setStyleSheet("color: #2e7d32; font-size: 13px;")
                self._bundle_valid = True
                self._update_buttons()
            else:
                self.message_label.setText(f"❌ Connection failed: {result.message}")
                self.message_label.setStyleSheet("color: #d32f2f; font-size: 13px;")
                self._bundle_valid = False
                self._update_buttons()
        except GitConfigValidationError as e:
            self.message_label.setText(f"❌ Invalid bundle: {str(e)}")
            self.message_label.setStyleSheet("color: #d32f2f; font-size: 13px;")
            self._bundle_valid = False
            self._update_buttons()
        except Exception as e:
            logger.exception("Test connection failed")
            self.message_label.setText(f"❌ Error: {str(e)}")
            self.message_label.setStyleSheet("color: #d32f2f; font-size: 13px;")
            self._bundle_valid = False
            self._update_buttons()
        finally:
            self.progress.setVisible(False)
            self._update_buttons()

    def _save_config(self) -> None:
        """Save the encrypted configuration."""
        bundle = self.bundle_edit.toPlainText().strip()
        if not bundle:
            QMessageBox.warning(self, "Error", "Please paste an encrypted configuration bundle.")
            return

        if not can_write(self._collaboration_manager):
            notify(self._notification_service, "You must be in WRITE mode to save Git configuration.", "warning")
            return

        try:
            self._git_config_service.save_encrypted_bundle(bundle)
            self._load_status()
            self.message_label.setText("✅ Configuration saved successfully!")
            self.message_label.setStyleSheet("color: #2e7d32; font-size: 13px;")
            self._bundle_valid = False
            self._update_buttons()
            self.config_changed.emit()

            if self._notification_service:
                notify(self._notification_service, "Git configuration updated.", "success")

            QMessageBox.information(self, "Success", "Git configuration saved successfully.")

        except GitConfigValidationError as e:
            QMessageBox.warning(self, "Validation Error", str(e))
        except Exception as e:
            logger.exception("Failed to save Git configuration")
            QMessageBox.critical(self, "Error", f"Failed to save configuration: {str(e)}")

    def refresh(self) -> None:
        """Refresh the page."""
        self._load_status()
        self._update_buttons()

    def set_write_enabled(self, enabled: bool) -> None:
        """Receive WRITE state from the workspace transaction controller."""
        self._write_enabled = bool(enabled)
        self._update_buttons()