# -*- coding: utf-8 -*-
"""Regression coverage for portable Git metadata and local DPAPI credentials."""

import json
from pathlib import Path

import centermanager.services.git_config_service as git_config_module
from centermanager.services.git_config_service import GitConfig, GitConfigService


REPOSITORY_URL = "https://github.com/example/center-manager.git"
USERNAME = "center-manager-service"
TOKEN = "test-token-never-persist-plaintext"


def _config() -> GitConfig:
    return GitConfig(
        repository_url=REPOSITORY_URL,
        username=USERNAME,
        token=TOKEN,
        branch="main",
        email="service@example.invalid",
    )


def test_save_config_splits_portable_metadata_from_local_secret(tmp_path, monkeypatch):
    config_path = tmp_path / "runtime" / "Config" / "config.json"
    service = GitConfigService(config_path=config_path)
    monkeypatch.setattr(service, "test_connection", lambda config: True)
    monkeypatch.setattr(service, "_protect_local_token", lambda token: "DPAPI:v2:LOCAL-ONLY")

    assert service.save_config(_config()) is True

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    git = raw["git"]
    assert git["repository_url"] == REPOSITORY_URL
    assert git["username"] == USERNAME
    assert git["branch"] == "main"
    assert git["token_secret"] == "DPAPI:v2:LOCAL-ONLY"
    assert "token" not in git
    assert TOKEN not in config_path.read_text(encoding="utf-8")
    assert "config" not in git


def test_portable_metadata_without_token_requires_local_provisioning(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "git": {
                    "repository_url": REPOSITORY_URL,
                    "username": USERNAME,
                    "branch": "main",
                    "email": "service@example.invalid",
                }
            }
        ),
        encoding="utf-8",
    )

    service = GitConfigService(config_path=config_path)

    assert service.has_config() is True
    assert service.credential_status() == "not_provisioned_on_this_machine"
    assert service.get_config() is None

    portable = service.get_portable_config()
    assert portable is not None
    assert portable.repository_url == REPOSITORY_URL
    assert portable.username == USERNAME
    assert portable.branch == "main"
    assert portable.token == ""


def test_foreign_local_secret_preserves_metadata_without_remote_attempt(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "git": {
                    "repository_url": REPOSITORY_URL,
                    "username": USERNAME,
                    "branch": "main",
                    "token_secret": "DPAPI:v2:FOREIGN-MACHINE-BLOB",
                }
            }
        ),
        encoding="utf-8",
    )

    service = GitConfigService(config_path=config_path)
    calls = {"remote": 0}

    def foreign_dpapi(_bundle):
        raise ValueError("foreign DPAPI context")

    def unexpected_remote(_config):
        calls["remote"] += 1
        return False

    monkeypatch.setattr(service, "_unprotect_local_token", foreign_dpapi)
    monkeypatch.setattr(service, "test_connection", unexpected_remote)

    assert service.credential_status() == "not_provisioned_on_this_machine"
    assert service.get_config() is None
    assert calls["remote"] == 0

    portable = service.get_portable_config()
    assert portable is not None
    assert portable.repository_url == REPOSITORY_URL
    assert portable.username == USERNAME


def test_local_provisioning_then_restart_loads_without_prompt(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    service = GitConfigService(config_path=config_path)
    monkeypatch.setattr(service, "test_connection", lambda config: True)
    monkeypatch.setattr(
        service,
        "_protect_local_token",
        lambda token: "DPAPI:v2:DESTINATION-LOCAL-BLOB",
    )

    assert service.save_config(_config()) is True

    restarted = GitConfigService(config_path=config_path)
    monkeypatch.setattr(
        restarted,
        "_unprotect_local_token",
        lambda bundle: TOKEN if bundle == "DPAPI:v2:DESTINATION-LOCAL-BLOB" else "",
    )

    assert restarted.credential_status() == "ready"
    loaded = restarted.get_config()
    assert loaded is not None
    assert loaded.repository_url == REPOSITORY_URL
    assert loaded.username == USERNAME
    assert loaded.token == TOKEN


def test_foreign_legacy_dpapi_is_reported_as_nonportable(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"git": {"config": "DPAPI:v2:FOREIGN-WHOLE-CONFIG"}}),
        encoding="utf-8",
    )

    def cannot_decrypt(_bundle):
        raise ValueError("different Windows user/machine")

    monkeypatch.setattr(git_config_module, "decrypt_git_config", cannot_decrypt)
    service = GitConfigService(config_path=config_path)

    assert service.has_config() is True
    assert service.credential_status() == "legacy_not_provisioned_on_this_machine"
    assert service.get_config() is None
    assert service.get_portable_config() is None

    validation = service.validate_bundle("DPAPI:v2:FOREIGN-WHOLE-CONFIG")
    assert validation.success is False
    assert "local" in validation.message.lower()


def test_git_config_dialog_provisions_plain_input_locally_instead_of_importing_dpapi_bundle():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/centermanager/ui/git_config_dialog.py").read_text(encoding="utf-8")

    assert "token_edit" in source
    assert "QLineEdit.EchoMode.Password" in source
    assert "save_config(config)" in source
    assert "bundle_edit" not in source
    assert "save_encrypted_bundle(bundle)" not in source


def test_bootstrap_reloads_config_after_local_provisioning():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "src/centermanager/platform/bootstrap/bootstrap_manager.py"
    ).read_text(encoding="utf-8")

    sync_marker = source.index("if not self._ensure_authoritative_runtime_database(paths):")
    reload_marker = source.index("config = load_config(paths.config_file)", sync_marker)
    context_marker = source.index("deployment_context = self._build_deployment_context(config)", reload_marker)
    assert sync_marker < reload_marker < context_marker
