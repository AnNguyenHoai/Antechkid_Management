# -*- coding: utf-8 -*-
"""
SettingsPage - System configuration.
Now with collaboration settings and tabs.
"""
import json
import logging
from typing import Optional
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QScrollArea, QFrame, QMessageBox, QLabel,
    QTabWidget, QSpinBox, QCheckBox
)

from centermanager.core.paths import get_paths
from centermanager.core.config import get_config, save_config
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.notification import NotificationService

logger = logging.getLogger(__name__)


class SettingsPage(QWidget):
    def __init__(
        self,
        collaboration_manager: CollaborationManager,
        notification_service: NotificationService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._collaboration_manager = collaboration_manager
        self._notification_service = notification_service
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(24, 24, 24, 24)
        container_layout.setSpacing(16)

        # Header
        header = QLabel("System Configuration")
        header.setStyleSheet("font-size: 20px; font-weight: bold;")
        container_layout.addWidget(header)

        # Tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: white;
            }
            QTabBar::tab {
                padding: 8px 16px;
                font-size: 14px;
            }
            QTabBar::tab:selected {
                font-weight: bold;
                color: #1976d2;
            }
        """)

        # General tab
        general_tab = self._create_general_tab()
        self.tab_widget.addTab(general_tab, "General")

        # Collaboration tab
        collab_tab = self._create_collaboration_tab()
        self.tab_widget.addTab(collab_tab, "Collaboration")

        container_layout.addWidget(self.tab_widget)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setFixedWidth(140)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background: #1976d2;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #1565c0;
            }
        """)
        self.save_btn.clicked.connect(self._save_settings)
        btn_layout.addWidget(self.save_btn)

        container_layout.addLayout(btn_layout)
        container_layout.addStretch()

        scroll.setWidget(container)
        layout.addWidget(scroll)

    def _create_general_tab(self) -> QWidget:
        """Create the General settings tab."""
        tab = QWidget()
        form_layout = QFormLayout(tab)
        form_layout.setSpacing(12)
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.center_name_edit = QLineEdit()
        form_layout.addRow("Center Name:", self.center_name_edit)

        self.address_edit = QLineEdit()
        form_layout.addRow("Address:", self.address_edit)

        self.phone_edit = QLineEdit()
        form_layout.addRow("Phone:", self.phone_edit)

        self.email_edit = QLineEdit()
        form_layout.addRow("Email:", self.email_edit)

        self.currency_edit = QLineEdit()
        self.currency_edit.setPlaceholderText("e.g., VND, USD")
        form_layout.addRow("Currency:", self.currency_edit)

        self.timezone_edit = QLineEdit()
        self.timezone_edit.setPlaceholderText("e.g., Asia/Ho_Chi_Minh")
        form_layout.addRow("Timezone:", self.timezone_edit)

        self.academic_year_edit = QLineEdit()
        self.academic_year_edit.setPlaceholderText("e.g., 2026-2027")
        form_layout.addRow("Academic Year:", self.academic_year_edit)

        return tab

    def _create_collaboration_tab(self) -> QWidget:
        """Create the Collaboration settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Heartbeat Interval
        self.heartbeat_interval = QSpinBox()
        self.heartbeat_interval.setRange(5, 120)
        self.heartbeat_interval.setSuffix(" s")
        self.heartbeat_interval.setToolTip("How often the application updates the heartbeat (seconds).")
        form.addRow("Heartbeat Interval:", self.heartbeat_interval)

        # Lock Timeout
        self.lock_timeout = QSpinBox()
        self.lock_timeout.setRange(10, 300)
        self.lock_timeout.setSuffix(" s")
        self.lock_timeout.setToolTip("Maximum time before a lock is considered stale (seconds).")
        form.addRow("Lock Timeout:", self.lock_timeout)

        # Retry Count
        self.retry_count = QSpinBox()
        self.retry_count.setRange(1, 10)
        self.retry_count.setToolTip("Number of retry attempts for Git operations.")
        form.addRow("Retry Count:", self.retry_count)

        # Backup before publish
        self.backup_before_publish = QCheckBox("Enable backup before publish")
        self.backup_before_publish.setToolTip("Create a backup before every publish operation.")
        form.addRow("", self.backup_before_publish)

        # Auto release (future)
        self.auto_release = QCheckBox("Auto-release lock after inactivity (future)")
        self.auto_release.setEnabled(False)
        form.addRow("", self.auto_release)

        layout.addLayout(form)
        layout.addStretch()

        # Load collaboration settings
        self._load_collaboration_settings()

        return tab

    def _load_settings(self) -> None:
        """Load general settings from config."""
        try:
            config = get_config()
            data = config.raw
            settings = data.get("system", {})
            self.center_name_edit.setText(settings.get("center_name", ""))
            self.address_edit.setText(settings.get("address", ""))
            self.phone_edit.setText(settings.get("phone", ""))
            self.email_edit.setText(settings.get("email", ""))
            self.currency_edit.setText(settings.get("currency", "VND"))
            self.timezone_edit.setText(settings.get("timezone", "Asia/Ho_Chi_Minh"))
            self.academic_year_edit.setText(settings.get("academic_year", ""))
        except Exception as e:
            logger.exception("Error loading general settings")

    def _load_collaboration_settings(self) -> None:
        """Load collaboration settings from config."""
        try:
            config = get_config()
            settings = config.get_collaboration_settings()
            self.heartbeat_interval.setValue(settings.get("heartbeat_interval", 10))
            self.lock_timeout.setValue(settings.get("lock_timeout", 60))
            self.retry_count.setValue(settings.get("retry_count", 3))
            self.backup_before_publish.setChecked(settings.get("backup_before_publish", True))
        except Exception as e:
            logger.exception("Error loading collaboration settings")

    def _save_settings(self) -> None:
        """Save all settings to config."""
        if not self._collaboration_manager.ensure_write():
            self._notification_service.notify("You must be in WRITE mode to save settings.", "warning")
            return

        try:
            config = get_config()
            data = config.raw

            # Save general settings
            data["system"] = {
                "center_name": self.center_name_edit.text().strip(),
                "address": self.address_edit.text().strip(),
                "phone": self.phone_edit.text().strip(),
                "email": self.email_edit.text().strip(),
                "currency": self.currency_edit.text().strip() or "VND",
                "timezone": self.timezone_edit.text().strip() or "Asia/Ho_Chi_Minh",
                "academic_year": self.academic_year_edit.text().strip(),
            }

            # Save collaboration settings
            data["collaboration"] = {
                "heartbeat_interval": self.heartbeat_interval.value(),
                "lock_timeout": self.lock_timeout.value(),
                "retry_count": self.retry_count.value(),
                "backup_before_publish": self.backup_before_publish.isChecked(),
                "auto_release": False,  # future
            }

            save_config(data)
            QMessageBox.information(self, "Success", "Settings saved successfully.")
            self._notification_service.notify("Settings updated.", "success")

        except Exception as e:
            logger.exception("Error saving settings")
            QMessageBox.critical(self, "Error", f"Could not save settings: {str(e)}")

    def set_write_enabled(self, enabled: bool) -> None:
        """Enable/disable save button based on write mode."""
        self.save_btn.setEnabled(enabled)