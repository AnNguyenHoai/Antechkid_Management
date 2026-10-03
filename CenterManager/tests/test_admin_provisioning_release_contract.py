# -*- coding: utf-8 -*-
"""Release contracts for the standalone administrator provisioning utility."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_release_builds_and_packages_admin_provisioning_executable():
    source = _read("build_release.py")
    assert 'ADMIN_TOOL_NAME = "GitProvisioningAdmin"' in source
    assert "def build_admin_provisioning_executable()" in source
    assert '"git_provisioning_admin.py"' in source
    assert 'admin_dir = PACKAGE_ROOT / "AdminTools"' in source
    assert "shutil.copy2(admin_executable, admin_dir / admin_executable.name)" in source
    assert '"admin_provisioning_tool": f"AdminTools/{ADMIN_TOOL_NAME}.exe"' in source


def test_admin_tool_uses_password_field_destination_crypto_and_existing_db_key():
    source = _read("git_provisioning_admin.py")
    assert "QLineEdit.EchoMode.Password" in source
    assert "create_bundle(request, payload)" in source
    assert '"token": token' in source
    assert "build_workstation_payload(git_payload, workspace_key)" in source
    assert "DatabaseKeyStore(bundle_path=_workspace_key_path(root)).load()" in source
    assert ".create()" not in source
    assert "self.token_edit.clear()" in source
    assert "--token" not in source


def test_admin_tool_selects_authorized_installation_instead_of_copying_dpapi():
    source = _read("git_provisioning_admin.py")
    assert 'form.addRow("Authorized installation:", authority_row)' in source
    assert "QFileDialog.getExistingDirectory" in source
    assert "_load_existing_workspace_key(authority_root)" in source
    assert '"runtime" / "Config" / "database_key.dpapi"' in source
    assert "database_key.dpapi file is not" in source
    assert "copied into the clean destination release" in source


def test_release_documents_no_python_admin_flow():
    source = _read("build_release.py")
    assert "AdminTools/GitProvisioningAdmin.exe" in source
    assert "destination-bound workstation bundle" in source
    assert "No source checkout or Python installation is required" in source
