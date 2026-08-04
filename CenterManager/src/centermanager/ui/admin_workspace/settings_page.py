# src/centermanager/ui/admin_workspace/settings_page.py
# -*- coding: utf-8 -*-
"""
SettingsPage - System configuration.
"""
import json
import logging
from typing import Optional
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QScrollArea, QFrame, QMessageBox, QLabel
)

from centermanager.core.paths import get_paths
from centermanager.core.config import get_config, save_config

logger = logging.getLogger(__name__)


class SettingsPage(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
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

        # Form
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
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

        container_layout.addWidget(form_widget)

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

    def _load_settings(self) -> None:
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
            logger.exception("Error loading settings")

    def _save_settings(self) -> None:
        try:
            config = get_config()
            data = config.raw
            data["system"] = {
                "center_name": self.center_name_edit.text().strip(),
                "address": self.address_edit.text().strip(),
                "phone": self.phone_edit.text().strip(),
                "email": self.email_edit.text().strip(),
                "currency": self.currency_edit.text().strip() or "VND",
                "timezone": self.timezone_edit.text().strip() or "Asia/Ho_Chi_Minh",
                "academic_year": self.academic_year_edit.text().strip(),
            }
            save_config(data)
            QMessageBox.information(self, "Success", "Settings saved successfully.")
        except Exception as e:
            logger.exception("Error saving settings")
            QMessageBox.critical(self, "Error", f"Could not save settings: {str(e)}")