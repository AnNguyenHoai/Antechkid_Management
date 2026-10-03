# -*- coding: utf-8 -*-
"""Destination-bound workstation provisioning without exposing secrets."""

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
    parse_provisioning_payload,
    provision_workspace_database_key,
    write_destination_request,
)

logger = logging.getLogger(__name__)


class GitConfigDialog(QDialog):
    """Provision destination Git access and, when required, the shared DB key."""

    config_saved = Signal()

    def __init__(
        self,
        git_config_service: GitConfigService,
        parent: Optional[QWidget] = None,
        *,
        require_database_key: bool = False,
    ) -> None:
        super().__init__(parent)
        self._git_config_service = git_config_service
        self._require_database_key = bool(require_database_key)
        self.setWindowTitle("Workstation Provisioning")
        self.setMinimumSize(660, 380)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        header = QLabel("🔐 Secure Workstation Provisioning")
        header.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(header)

        secret_description = (
            "Git credential and the shared encrypted-database workspace key"
            if self._require_database_key
            else "Git credential"
        )
        desc = QLabel(
            f"This Windows user/machine does not yet have usable {secret_description}.\n\n"
            "1. Export a provisioning request and send only that public request to the administrator.\n"
            "2. Ask the administrator to create a destination-bound workstation bundle from an "
            "already-authorized CenterManager installation.\n"
            "3. Import the encrypted bundle returned by the administrator.\n\n"
            "Secrets are never displayed or entered on this computer. After import they are "
            "protected locally with Windows DPAPI."
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
            "Provisioning status: secrets are not ready for this Windows identity."
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
        return self._git_config_service._config_path

    def _export_request(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Workstation Provisioning Request",
            "CenterManager_Workstation_Provisioning_Request.json",
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
            logger.exception("Failed to export workstation provisioning request")
            QMessageBox.critical(self, "Export Error", "Could not create the provisioning request.")

    def _import_bundle(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Workstation Provisioning Bundle",
            "",
            "JSON files (*.json)",
        )
        if not path:
            return

        config = None
        payload = None
        workspace_key = None
        git_payload = None
        try:
            bundle = json.loads(Path(path).read_text(encoding="utf-8"))
            payload = decrypt_bundle(self._config_path, bundle)
            git_payload, workspace_key = parse_provisioning_payload(payload)

            if self._require_database_key and workspace_key is None:
                raise ProvisioningError(
                    "This legacy Git-only bundle does not contain the shared workspace database key. "
                    "Ask the administrator to create a new workstation provisioning bundle."
                )

            # Re-wrap the authenticated shared key for this destination first.
            # The helper refuses to replace a different valid local workspace key,
            # but can repair a copied foreign-DPAPI bundle.
            if workspace_key is not None:
                provision_workspace_database_key(workspace_key)

            config = GitConfig.from_dict(git_payload)
            # save_config validates the remote before persisting and stores the
            # token only as destination-local DPAPI secret material.
            if not self._git_config_service.save_config(config):
                raise ProvisioningError(
                    "The encrypted credential was opened, but Git validation failed."
                )

            self.status_label.setText("✅ Workstation secrets provisioned successfully.")
            self.status_label.setStyleSheet("color: #2e7d32; font-size: 13px;")
            self.config_saved.emit()
            self.accept()
        except (ProvisioningError, ValueError, KeyError, json.JSONDecodeError) as exc:
            logger.warning("Workstation provisioning bundle rejected: %s", exc)
            QMessageBox.warning(self, "Provisioning Failed", str(exc))
        except Exception:
            logger.exception("Failed to import workstation provisioning bundle")
            QMessageBox.critical(self, "Provisioning Error", "Could not provision this workstation.")
        finally:
            config = None
            payload = None
            workspace_key = None
            git_payload = None
