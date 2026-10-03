# -*- coding: utf-8 -*-
"""Standalone admin UI for creating destination-bound workstation bundles."""

import json
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from centermanager.core.version import get_release_root
from centermanager.database.encryption import DatabaseKeyStore, DatabaseKeyUnavailable
from centermanager.services.git_provisioning import (
    ProvisioningError,
    build_workstation_payload,
    create_bundle,
)


def _package_root() -> Path:
    """Locate the canonical CenterManager release/source root."""
    return get_release_root()


def _workspace_key_path(installation_root: Path) -> Path:
    """Return the local DPAPI workspace-key path for an installation root."""
    return Path(installation_root).resolve() / "runtime" / "Config" / "database_key.dpapi"


def _load_existing_workspace_key(installation_root: Path | None = None) -> bytes:
    """Load an already-authorized shared key; never create a replacement key."""
    root = Path(installation_root).resolve() if installation_root is not None else _package_root()
    return DatabaseKeyStore(bundle_path=_workspace_key_path(root)).load()


class ProvisioningAdminWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AN TECHKIDS - Workstation Provisioning Admin")
        self.setMinimumWidth(680)

        self.request_edit = QLineEdit()
        self.authority_root_edit = QLineEdit(str(_package_root()))
        self.repository_edit = QLineEdit()
        self.username_edit = QLineEdit()
        self.token_edit = QLineEdit()
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.branch_edit = QLineEdit("main")
        self.email_edit = QLineEdit()

        browse = QPushButton("Browse...")
        browse.clicked.connect(self._browse_request)
        request_row = QHBoxLayout()
        request_row.addWidget(self.request_edit)
        request_row.addWidget(browse)

        authority_browse = QPushButton("Browse...")
        authority_browse.clicked.connect(self._browse_authority_root)
        authority_row = QHBoxLayout()
        authority_row.addWidget(self.authority_root_edit)
        authority_row.addWidget(authority_browse)

        form = QFormLayout()
        form.addRow("Provisioning request:", request_row)
        form.addRow("Authorized installation:", authority_row)
        form.addRow("Repository URL:", self.repository_edit)
        form.addRow("Username:", self.username_edit)
        form.addRow("Git PAT:", self.token_edit)
        form.addRow("Branch:", self.branch_edit)
        form.addRow("Email:", self.email_edit)

        create = QPushButton("Create Encrypted Workstation Bundle")
        create.clicked.connect(self._create_bundle)

        note = QLabel(
            "Select a CenterManager installation on this Windows user/machine that can already "
            "open the production database. The tool loads that installation's existing shared "
            "workspace database key and combines it with the Git credential only in memory. "
            "No new database key is generated, and the protected database_key.dpapi file is not "
            "copied into the clean destination release."
        )
        note.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addWidget(create)

    def _browse_request(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select CenterManager Provisioning Request",
            "",
            "JSON files (*.json);;All files (*)",
        )
        if filename:
            self.request_edit.setText(filename)

    def _browse_authority_root(self) -> None:
        start = self.authority_root_edit.text().strip() or str(_package_root())
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Authorized CenterManager Installation",
            start,
        )
        if directory:
            self.authority_root_edit.setText(directory)

    def _create_bundle(self) -> None:
        request_path = Path(self.request_edit.text().strip())
        authority_text = self.authority_root_edit.text().strip()
        repository_url = self.repository_edit.text().strip()
        username = self.username_edit.text().strip()
        token = self.token_edit.text().strip()
        branch = self.branch_edit.text().strip() or "main"
        email = self.email_edit.text().strip()
        workspace_key = None

        if not request_path.is_file():
            QMessageBox.warning(self, "Missing request", "Select a valid provisioning request JSON file.")
            return
        if not authority_text:
            QMessageBox.warning(
                self,
                "Missing authorized installation",
                "Select a CenterManager installation that can already open the production database.",
            )
            return
        authority_root = Path(authority_text).resolve()
        if not authority_root.is_dir():
            QMessageBox.warning(
                self,
                "Invalid authorized installation",
                "The selected CenterManager installation directory does not exist.",
            )
            return
        if not repository_url or not username or not token:
            QMessageBox.warning(self, "Missing fields", "Repository URL, username, and Git PAT are required.")
            return

        output_name = request_path.with_name("CenterManager_Workstation_Provisioning_Bundle.json")
        output, _ = QFileDialog.getSaveFileName(
            self,
            "Save Encrypted Workstation Provisioning Bundle",
            str(output_name),
            "JSON files (*.json);;All files (*)",
        )
        if not output:
            return

        try:
            request = json.loads(request_path.read_text(encoding="utf-8"))
            workspace_key = _load_existing_workspace_key(authority_root)
            git_payload = {
                "repository_url": repository_url,
                "username": username,
                "token": token,
                "branch": branch,
                "email": email,
                "allow_local_file_remote": False,
            }
            payload = build_workstation_payload(git_payload, workspace_key)
            bundle = create_bundle(request, payload)
            Path(output).write_text(json.dumps(bundle, indent=2), encoding="utf-8")
        except DatabaseKeyUnavailable as exc:
            key_path = _workspace_key_path(authority_root)
            QMessageBox.critical(
                self,
                "Workspace key unavailable",
                "The selected administrator installation does not have a usable workspace database key. "
                "Select an installation on this Windows user/machine that can already open the production "
                "database. A new key will not be generated.\n\n"
                f"Expected protected key: {key_path}\n\n{exc}",
            )
            return
        except (OSError, json.JSONDecodeError, ProvisioningError, ValueError) as exc:
            QMessageBox.critical(self, "Provisioning failed", str(exc))
            return
        finally:
            self.token_edit.clear()
            token = ""
            workspace_key = None

        QMessageBox.information(
            self,
            "Bundle created",
            "Encrypted destination-bound workstation provisioning bundle created successfully.",
        )


def main() -> int:
    app = QApplication(sys.argv)
    window = ProvisioningAdminWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
