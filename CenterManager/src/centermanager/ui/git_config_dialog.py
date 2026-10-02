# -*- coding: utf-8 -*-
"""Git configuration provisioning without exposing the Git token to operators."""

import json
import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from centermanager.services.git_config_service import GitConfig, GitConfigService
from centermanager.services.git_provisioning import (
    ProvisioningError,
    decrypt_bundle,
    write_destination_request,
)

logger = logging.getLogger(__name__)


class GitConfigDialog(QDialog):
    """Provision one destination from an administrator-created encrypted bundle.

    The destination exports only a public-key request. The administrator uses
    that request to encrypt the Git configuration. The Git token exists as
    plaintext only transiently inside this process after bundle decryption and
    is immediately re-wrapped with the destination Windows user's DPAPI store.
    """

    config_saved = Signal()

    def __init__(
        self,
        git_config_service: GitConfigService,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._git_config_service = git_config_service
        self.setWindowTitle("Git Provisioning")
        self.setMinimumSize(640, 360)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        header = QLabel("🔐 Secure Git Provisioning")
        header.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(header)

        desc = QLabel(
            "This Windows user/machine does not yet have a usable Git credential.\n\n"
            "1. Export a provisioning request and send that request to the administrator. "
            "It contains only a public key and no secret.\n"
            "2. Import the encrypted provisioning bundle returned by the administrator.\n\n"
            "The Git token is never displayed or entered on this computer. After import, "
            "it is protected locally with Windows DPAPI."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #555; font-size: 13px;")
        layout.addWidget(desc)

        portable = self._git_config_service.get_portable_config()
        if portable is not None:
            metadata = QLabel(
                f"Repository: {portable.repository_url}\n"
                f"Username: {portable.username}\n"
                f"Branch: {portable.branch or 'main'}"
            )
            metadata.setWordWrap(True)
            metadata.setStyleSheet("background: #f4f6f8; padding: 10px; border-radius: 4px;")
            layout.addWidget(metadata)

        self.status_label = QLabel(
            "Credential status: not provisioned for this Windows identity."
        )
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #a15c00; font-size: 13px;")
        layout.addWidget(self.status_label)

        buttons = QHBoxLayout()
        self.export_btn = QPushButton("Export Provisioning Request…")
        self.import_btn = QPushButton("Import Encrypted Bundle…")
        self.cancel_btn = QPushButton("Cancel")
        buttons.addWidget(self.export_btn)
        buttons.addWidget(self.import_btn)
        buttons.addStretch()
        buttons.addWidget(self.cancel_btn)
        layout.addLayout(buttons)
        layout.addStretch()

        self.export_btn.clicked.connect(self._export_request)
        self.import_btn.clicked.connect(self._import_bundle)
        self.cancel_btn.clicked.connect(self.reject)

    @property
    def _config_path(self) -> Path:
        # Keep the provisioning identity next to the local config used by the
        # service, without exposing a new public persistence contract.
        return self._git_config_service._config_path

    def _export_request(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Git Provisioning Request",
            "CenterManager_Git_Provisioning_Request.json",
            "JSON files (*.json)",
        )
        if not path:
            return
        try:
            write_destination_request(self._config_path, Path(path))
            self.status_label.setText(
                "✅ Provisioning request exported. Send this public request to the administrator."
            )
            self.status_label.setStyleSheet("color: #2e7d32; font-size: 13px;")
        except Exception:
            logger.exception("Failed to export Git provisioning request")
            QMessageBox.critical(self, "Export Error", "Could not create the provisioning request.")

    def _import_bundle(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Git Provisioning Bundle",
            "",
            "JSON files (*.json)",
        )
        if not path:
            return

        config = None
        payload = None
        try:
            bundle = json.loads(Path(path).read_text(encoding="utf-8"))
            payload = decrypt_bundle(self._config_path, bundle)
            config = GitConfig.from_dict(payload)

            # save_config validates the remote before persisting. On success it
            # stores only portable metadata plus a DPAPI-wrapped local token.
            if not self._git_config_service.save_config(config):
                raise ProvisioningError(
                    "The encrypted credential was opened, but Git validation failed."
                )

            self.status_label.setText("✅ Git credential provisioned successfully.")
            self.status_label.setStyleSheet("color: #2e7d32; font-size: 13px;")
            self.config_saved.emit()
            self.accept()
        except (ProvisioningError, ValueError, KeyError, json.JSONDecodeError) as exc:
            logger.warning("Git provisioning bundle rejected: %s", exc)
            QMessageBox.warning(
                self,
                "Provisioning Failed",
                "The bundle is invalid, belongs to another destination, or the Git credential failed validation.",
            )
        except Exception:
            logger.exception("Failed to import Git provisioning bundle")
            QMessageBox.critical(self, "Provisioning Error", "Could not provision Git access.")
        finally:
            # Best-effort removal of references to plaintext credential objects.
            config = None
            payload = None
