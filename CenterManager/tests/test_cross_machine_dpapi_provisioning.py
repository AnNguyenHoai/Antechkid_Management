# -*- coding: utf-8 -*-
"""Regression coverage for cross-machine Git credential provisioning."""

import json
from pathlib import Path

import centermanager.services.git_config_service as git_config_module
from centermanager.services.git_config_service import GitConfig, GitConfigService
from centermanager.services.git_provisioning import (
    ProvisioningError,
    create_bundle,
    decrypt_bundle,
    ensure_destination_request,
)

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
    assert git["token_secret"] == "DPAPI:v2:LOCAL-ONLY"
    assert "token" not in git
    assert TOKEN not in config_path.read_text(encoding="utf-8")


def test_portable_metadata_without_token_requires_local_provisioning(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"git": {
        "repository_url": REPOSITORY_URL,
        "username": USERNAME,
        "branch": "main",
    }}), encoding="utf-8")
    service = GitConfigService(config_path=config_path)
    assert service.has_config() is True
    assert service.credential_status() == "not_provisioned_on_this_machine"
    assert service.get_config() is None
    assert service.get_portable_config().repository_url == REPOSITORY_URL


def test_foreign_local_secret_preserves_metadata_without_remote_attempt(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"git": {
        "repository_url": REPOSITORY_URL,
        "username": USERNAME,
        "branch": "main",
        "token_secret": "DPAPI:v2:FOREIGN-MACHINE-BLOB",
    }}), encoding="utf-8")
    service = GitConfigService(config_path=config_path)
    calls = {"remote": 0}
    monkeypatch.setattr(service, "_unprotect_local_token", lambda _bundle: (_ for _ in ()).throw(ValueError("foreign")))
    monkeypatch.setattr(service, "test_connection", lambda _config: calls.__setitem__("remote", calls["remote"] + 1))
    assert service.credential_status() == "not_provisioned_on_this_machine"
    assert service.get_config() is None
    assert calls["remote"] == 0
    assert service.get_portable_config().repository_url == REPOSITORY_URL


def test_local_provisioning_then_restart_loads_without_prompt(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    service = GitConfigService(config_path=config_path)
    monkeypatch.setattr(service, "test_connection", lambda config: True)
    monkeypatch.setattr(service, "_protect_local_token", lambda token: "DPAPI:v2:DESTINATION-LOCAL-BLOB")
    assert service.save_config(_config()) is True
    restarted = GitConfigService(config_path=config_path)
    monkeypatch.setattr(restarted, "_unprotect_local_token", lambda bundle: TOKEN)
    assert restarted.credential_status() == "ready"
    assert restarted.get_config().token == TOKEN


def test_foreign_legacy_dpapi_is_reported_as_nonportable(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"git": {"config": "DPAPI:v2:FOREIGN-WHOLE-CONFIG"}}), encoding="utf-8")
    monkeypatch.setattr(git_config_module, "decrypt_git_config", lambda _bundle: (_ for _ in ()).throw(ValueError("foreign")))
    service = GitConfigService(config_path=config_path)
    assert service.credential_status() == "legacy_not_provisioned_on_this_machine"
    assert service.get_config() is None


def test_destination_bound_bundle_round_trip_and_wrong_destination_rejected(tmp_path):
    config_a = tmp_path / "a" / "config.json"
    config_b = tmp_path / "b" / "config.json"
    request_a = ensure_destination_request(config_a)
    ensure_destination_request(config_b)
    payload = _config().to_dict()

    bundle = create_bundle(request_a, payload)
    encoded = json.dumps(bundle)
    assert TOKEN not in encoded
    assert REPOSITORY_URL not in encoded

    opened = decrypt_bundle(config_a, bundle)
    assert opened["token"] == TOKEN
    assert opened["repository_url"] == REPOSITORY_URL

    try:
        decrypt_bundle(config_b, bundle)
        assert False, "bundle for destination A must not decrypt on destination B"
    except ProvisioningError:
        pass


def test_provisioning_private_key_is_not_plaintext(tmp_path):
    config_path = tmp_path / "runtime" / "Config" / "config.json"
    request = ensure_destination_request(config_path)
    private_record = config_path.parent / "git_provisioning_private.json"
    text = private_record.read_text(encoding="utf-8")
    assert "PRIVATE KEY-----" not in text
    assert "PUBLIC KEY-----" in request["public_key"]


def test_git_config_dialog_never_requests_plaintext_token():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/centermanager/ui/git_config_dialog.py").read_text(encoding="utf-8")
    assert "token_edit" not in source
    assert "QLineEdit" not in source
    assert "Export Provisioning Request" in source
    assert "Import Encrypted Bundle" in source
    assert "decrypt_bundle" in source
    assert "save_config(config)" in source


def test_admin_tool_uses_hidden_token_prompt_not_cli_token_argument():
    root = Path(__file__).resolve().parents[1]
    source = (root / "tools/create_git_provisioning_bundle.py").read_text(encoding="utf-8")
    assert "getpass.getpass" in source
    assert "--token" not in source


def test_bootstrap_reloads_config_after_local_provisioning():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/centermanager/platform/bootstrap/bootstrap_manager.py").read_text(encoding="utf-8")
    sync_marker = source.index("if not self._ensure_authoritative_runtime_database(paths):")
    reload_marker = source.index("config = load_config(paths.config_file)", sync_marker)
    context_marker = source.index("deployment_context = self._build_deployment_context(config)", reload_marker)
    assert sync_marker < reload_marker < context_marker
