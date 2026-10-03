# -*- coding: utf-8 -*-
"""Regression coverage for destination-bound workspace database-key provisioning."""

from pathlib import Path

import pytest

from centermanager.database.encryption import DatabaseKeyUnavailable
from centermanager.services.git_provisioning import (
    ProvisioningError,
    build_workstation_payload,
    parse_provisioning_payload,
    provision_workspace_database_key,
)


ROOT = Path(__file__).resolve().parents[1]
KEY_A = b"A" * 32
KEY_B = b"B" * 32
GIT_PAYLOAD = {
    "repository_url": "https://github.com/example/center-manager.git",
    "username": "service-user",
    "token": "secret-test-token",
    "branch": "main",
    "email": "service@example.invalid",
    "allow_local_file_remote": False,
}


class FakeKeyStore:
    def __init__(self, path: Path, *, loaded=None, load_error=False):
        self.bundle_path = path
        self.loaded = loaded
        self.load_error = load_error
        self.provision_calls = []

    def load(self):
        if self.load_error:
            raise DatabaseKeyUnavailable("foreign DPAPI")
        if self.loaded is None:
            raise DatabaseKeyUnavailable("missing")
        return self.loaded

    def provision(self, key, *, overwrite=False):
        self.provision_calls.append((key, overwrite))
        self.loaded = key
        self.load_error = False
        self.bundle_path.parent.mkdir(parents=True, exist_ok=True)
        self.bundle_path.write_text("protected", encoding="utf-8")
        return key


def test_v2_payload_round_trip_carries_existing_workspace_key():
    payload = build_workstation_payload(GIT_PAYLOAD, KEY_A)
    git_payload, key = parse_provisioning_payload(payload)
    assert git_payload == GIT_PAYLOAD
    assert key == KEY_A
    assert KEY_A.decode("ascii") not in str(payload)


def test_legacy_v1_payload_remains_git_only():
    git_payload, key = parse_provisioning_payload(dict(GIT_PAYLOAD))
    assert git_payload == GIT_PAYLOAD
    assert key is None


def test_v2_rejects_malformed_workspace_key():
    payload = build_workstation_payload(GIT_PAYLOAD, KEY_A)
    payload["workspace_database_key"] = "QQ=="
    with pytest.raises(ProvisioningError, match="256 bits"):
        parse_provisioning_payload(payload)


def test_missing_local_key_is_provisioned_without_overwrite(tmp_path):
    store = FakeKeyStore(tmp_path / "database_key.dpapi")
    provision_workspace_database_key(KEY_A, key_store=store)
    assert store.provision_calls == [(KEY_A, False)]
    assert store.load() == KEY_A


def test_foreign_dpapi_bundle_is_rewrapped_after_authenticated_import(tmp_path):
    path = tmp_path / "database_key.dpapi"
    path.write_text("DBKEY:v1:FOREIGN", encoding="utf-8")
    store = FakeKeyStore(path, load_error=True)
    provision_workspace_database_key(KEY_A, key_store=store)
    assert store.provision_calls == [(KEY_A, True)]
    assert store.load() == KEY_A


def test_different_valid_local_workspace_key_is_never_overwritten(tmp_path):
    path = tmp_path / "database_key.dpapi"
    path.write_text("protected", encoding="utf-8")
    store = FakeKeyStore(path, loaded=KEY_B)
    with pytest.raises(ProvisioningError, match="refusing to overwrite"):
        provision_workspace_database_key(KEY_A, key_store=store)
    assert store.provision_calls == []
    assert store.load() == KEY_B


def test_same_valid_local_workspace_key_is_noop(tmp_path):
    path = tmp_path / "database_key.dpapi"
    path.write_text("protected", encoding="utf-8")
    store = FakeKeyStore(path, loaded=KEY_A)
    provision_workspace_database_key(KEY_A, key_store=store)
    assert store.provision_calls == []


def test_admin_tool_loads_existing_key_and_never_creates_one():
    source = (ROOT / "git_provisioning_admin.py").read_text(encoding="utf-8")
    assert "DatabaseKeyStore(bundle_path=bundle_path).load()" in source
    assert ".create()" not in source
    assert "build_workstation_payload" in source


def test_bootstrap_routes_missing_or_foreign_database_key_to_provisioning():
    source = (ROOT / "src/centermanager/platform/bootstrap/bootstrap_manager.py").read_text(encoding="utf-8")
    assert "database_key_needs_provisioning" in source
    assert "except DatabaseKeyUnavailable" in source
    assert "require_database_key=database_key_needs_provisioning" in source
    assert "Workspace database key is still unavailable after provisioning" in source


def test_release_excludes_machine_bound_secret_material():
    source = (ROOT / "build_release.py").read_text(encoding="utf-8")
    assert '"*.dpapi"' in source
    assert '"git_provisioning_private.json"' in source
    assert '"config.json"' in source
    assert "Release packages intentionally contain no config.json" in source
