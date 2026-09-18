# -*- coding: utf-8 -*-
"""SEC-HOTFIX credential-remediation regression contracts."""

from pathlib import Path

from centermanager.core.git_url_safety import sanitize_repository_url

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_http_repository_credentials_are_removed_from_persisted_url():
    assert sanitize_repository_url("https://user:SECRET@example.com/org/repo.git") == "https://example.com/org/repo.git"
    assert sanitize_repository_url("https://TOKEN@example.com/org/repo.git") == "https://example.com/org/repo.git"


def test_ssh_repository_identity_is_not_removed():
    assert sanitize_repository_url("git@github.com:org/repo.git") == "git@github.com:org/repo.git"


def test_runtime_config_is_gitignored():
    source = _read(".gitignore")
    assert "runtime/Config/" in source
    assert "**/runtime/Config/config.json" in source


def test_windows_new_secret_path_uses_dpapi_not_legacy_static_key():
    source = _read("src/centermanager/core/crypto.py")
    encrypt_block = source[source.index("def encrypt_git_config"):source.index("def decrypt_git_config")]
    assert 'if os.name == "nt"' in encrypt_block
    assert "protect_secret(plaintext)" in encrypt_block
    assert "_encrypt_legacy" not in encrypt_block.split('if os.name == "nt":', 1)[0]


def test_legacy_bundle_is_one_way_migrated_on_windows():
    source = _read("src/centermanager/services/git_config_service.py")
    assert 'os.name == "nt" and encrypted.startswith("ENC:v1:")' in source
    assert "Migrated legacy Git credentials to Windows DPAPI" in source


def test_origin_reconciliation_never_persists_http_userinfo():
    source = _read("src/centermanager/platform/synchronization/git_origin_reconciliation.py")
    assert "sanitize_repository_url" in source
    assert "set_url(configured)" in source
    assert "provider._repository_url = configured" in source


def test_dpapi_store_contains_no_application_wide_secret():
    source = _read("src/centermanager/core/secret_store.py")
    assert "CryptProtectData" in source
    assert "CryptUnprotectData" in source
    assert "Secret-Key" not in source
    assert "TOKEN" not in source
