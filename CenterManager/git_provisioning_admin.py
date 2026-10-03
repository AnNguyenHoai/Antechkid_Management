# -*- coding: utf-8 -*-
"""Standalone admin UI for creating destination-bound Git provisioning bundles."""

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

from centermanager.services.git_provisioning import ProvisioningError, create_bundle


class ProvisioningAdminWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AN TECHKIDS - Git Provisioning Admin")
        self.setMinimumWidth(620)

        self.request_edit = QLineEdit()
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

        form = QFormLayout()
        form.addRow("Provisioning request:", request_row)
        form.addRow("Repository URL:", self.repository_edit)
        form.addRow("Username:", self.username_edit)
        form.addRow("Git PAT:", self.token_edit)
        form.addRow("Branch:", self.branch_edit)
        form.addRow("Email:", self.email_edit)

        create = QPushButton("Create Encrypted Bundle")
        create.clicked.connect(self._create_bundle)

        note = QLabel(
            "The PAT is used only in memory. The output bundle is encrypted for "
            "the selected destination request and cannot be opened by another machine."
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

    def _create_bundle(self) -> None:
        request_path = Path(self.request_edit.text().strip())
        repository_url = self.repository_edit.text().strip()
        username = self.username_edit.text().strip()
        token = self.token_edit.text().strip()
        branch = self.branch_edit.text().strip() or "main"
        email = self.email_edit.text().strip()

        if not request_path.is_file():
            QMessageBox.warning(self, "Missing request", "Select a valid provisioning request JSON file.")
            return
        if not repository_url or not username or not token:
            QMessageBox.warning(self, "Missing fields", "Repository URL, username, and Git PAT are required.")
            return

        output_name = request_path.with_name("CenterManager_Git_Provisioning_Bundle.json")
        output, _ = QFileDialog.getSaveFileName(
            self,
            "Save Encrypted Provisioning Bundle",
            str(output_name),
            "JSON files (*.json);;All files (*)",
        )
        if not output:
            return

        try:
            request = json.loads(request_path.read_text(encoding="utf-8"))
            payload = {
                "repository_url": repository_url,
                "username": username,
                "token": token,
                "branch": branch,
                "email": email,
                "allow_local_file_remote": False,
            }
            bundle = create_bundle(request, payload)
            Path(output).write_text(json.dumps(bundle, indent=2), encoding="utf-8")
        except (OSError, json.JSONDecodeError, ProvisioningError, ValueError) as exc:
            QMessageBox.critical(self, "Provisioning failed", str(exc))
            return
        finally:
            self.token_edit.clear()
            token = ""

        QMessageBox.information(
            self,
            "Bundle created",
            "Encrypted destination-bound provisioning bundle created successfully.",
        )


def main() -> int:
    app = QApplication(sys.argv)
    window = ProvisioningAdminWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
