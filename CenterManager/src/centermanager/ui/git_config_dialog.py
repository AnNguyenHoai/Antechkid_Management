# -*- coding: utf-8 -*-
"""GitConfigDialog - local Git credential provisioning dialog."""

import logging
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QProgressBar,
    QWidget,
)

from centermanager.services.git_config_service import GitConfig, GitConfigService

logger = logging.getLogger(__name__)


class GitConfigDialog(QDialog):
    """Provision Git credentials for the current Windows user/machine.

    Repository metadata may be copied with a portable deployment.  The access
    token is intentionally entered once on each destination Windows identity and
    is persisted through that identity's local secret store (DPAPI on Windows).
    """

    config_saved = Signal()

    def __init__(
        self,
        git_config_service: GitConfigService,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._git_config_service = git_config_service
        self._connection_test_passed = False

        self.setWindowTitle("Git Configuration")
        self.setMinimumSize(620, 440)
        self.setModal(True)

        self._setup_ui()
        self._prefill_portable_metadata()
        self._connect_signals()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        header = QLabel("🔐 Git Configuration")
        header.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(header)

        desc = QLabel(
            "Configure access to the authoritative Git repository.\n"
            "Repository settings can move with the application, but the access token "
            "is protected locally and must be provisioned once for each Windows user/machine."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; font-size: 13px;")
        layout.addWidget(desc)

        self.machine_notice = QLabel()
        self.machine_notice.setWordWrap(True)
        self.machine_notice.setStyleSheet("color: #a15c00; font-size: 13px;")
        layout.addWidget(self.machine_notice)

        form = QFormLayout()
        form.setSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.repository_url_edit = QLineEdit()
        self.repository_url_edit.setPlaceholderText("https://github.com/owner/repository.git")
        form.addRow("Repository URL:", self.repository_url_edit)

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("GitHub username")
        form.addRow("Username:", self.username_edit)

        self.token_edit = QLineEdit()
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_edit.setPlaceholderText("Access token for this machine")
        form.addRow("Access Token:", self.token_edit)

        self.branch_edit = QLineEdit("main")
        form.addRow("Branch:", self.branch_edit)

        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("Optional Git commit email")
        form.addRow("Email:", self.email_edit)

        layout.addLayout(form)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("font-size: 13px;")
        layout.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.test_btn = QPushButton("🔍 Test Connection")
        self.test_btn.setFixedHeight(34)
        btn_layout.addWidget(self.test_btn)

        btn_layout.addStretch()

        self.save_btn = QPushButton("💾 Save")
        self.save_btn.setFixedHeight(34)
        self.save_btn.setStyleSheet(
            """
            QPushButton {
                background: #1976d2;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: 500;
            }
            QPushButton:hover { background: #1565c0; }
            QPushButton:disabled { background: #b0b0b0; }
            """
        )
        self.save_btn.setEnabled(False)
        btn_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedHeight(34)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()

    def _prefill_portable_metadata(self) -> None:
        portable = self._git_config_service.get_portable_config()
        if portable is not None:
            self.repository_url_edit.setText(portable.repository_url)
            self.username_edit.setText(portable.username)
            self.branch_edit.setText(portable.branch or "main")
            self.email_edit.setText(portable.email or "")

        status = self._git_config_service.credential_status()
        if status in (
            "not_provisioned_on_this_machine",
            "legacy_not_provisioned_on_this_machine",
        ):
            self.machine_notice.setText(
                "This application was copied from another Windows user/machine. "
                "Its protected Git token cannot be reused here. Enter the token once "
                "to provision this machine; it will be protected locally."
            )
        elif status == "not_configured":
            self.machine_notice.setText(
                "Git access has not been configured on this machine yet."
            )
        else:
            self.machine_notice.clear()

    def _connect_signals(self) -> None:
        self.test_btn.clicked.connect(self._test_connection)
        self.save_btn.clicked.connect(self._save_config)
        self.cancel_btn.clicked.connect(self.reject)
        for edit in (
            self.repository_url_edit,
            self.username_edit,
            self.token_edit,
            self.branch_edit,
            self.email_edit,
        ):
            edit.textChanged.connect(self._on_config_changed)

    def _on_config_changed(self) -> None:
        self._connection_test_passed = False
        self.save_btn.setEnabled(False)
        self.status_label.clear()

    def _build_config(self) -> Optional[GitConfig]:
        repository_url = self.repository_url_edit.text().strip()
        username = self.username_edit.text().strip()
        token = self.token_edit.text().strip()
        branch = self.branch_edit.text().strip() or "main"
        email = self.email_edit.text().strip()

        if not repository_url or not username or not token:
            self.status_label.setText(
                "⚠️ Repository URL, username, and access token are required."
            )
            self.status_label.setStyleSheet("color: #d32f2f; font-size: 13px;")
            return None

        return GitConfig(
            repository_url=repository_url,
            username=username,
            token=token,
            branch=branch,
            email=email,
        )

    def _test_connection(self) -> None:
        config = self._build_config()
        if config is None:
            return

        self.progress.setVisible(True)
        self.test_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.status_label.setText("⏳ Testing connection...")
        self.status_label.setStyleSheet("color: #1976d2; font-size: 13px;")

        try:
            if self._git_config_service.test_connection(config):
                self._connection_test_passed = True
                self.status_label.setText("✅ Connection successful!")
                self.status_label.setStyleSheet("color: #2e7d32; font-size: 13px;")
                self.save_btn.setEnabled(True)
            else:
                self._connection_test_passed = False
                self.status_label.setText(
                    "❌ Connection failed. Check repository URL, username, token, and network access."
                )
                self.status_label.setStyleSheet("color: #d32f2f; font-size: 13px;")
        except Exception:
            logger.exception("Test connection failed")
            self._connection_test_passed = False
            self.status_label.setText("❌ Connection test failed.")
            self.status_label.setStyleSheet("color: #d32f2f; font-size: 13px;")
        finally:
            self.progress.setVisible(False)
            self.test_btn.setEnabled(True)

    def _save_config(self) -> None:
        config = self._build_config()
        if config is None:
            return

        if not self._connection_test_passed:
            QMessageBox.warning(
                self,
                "Test Required",
                "Please test the Git connection successfully before saving.",
            )
            return

        try:
            # save_config performs its own validation/test as a security boundary;
            # the UI test above is only interactive feedback.
            if not self._git_config_service.save_config(config):
                QMessageBox.warning(
                    self,
                    "Validation Error",
                    "Git configuration could not be validated or saved.",
                )
                return
            self.token_edit.clear()
            self.status_label.setText("✅ Configuration saved successfully!")
            self.status_label.setStyleSheet("color: #2e7d32; font-size: 13px;")
            self.config_saved.emit()
            self.accept()
        except Exception:
            logger.exception("Failed to save Git configuration")
            QMessageBox.critical(
                self,
                "Error",
                "Failed to save Git configuration on this machine.",
            )
