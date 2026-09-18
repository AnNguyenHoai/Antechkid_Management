import sys

import pytest

from centermanager.core.crypto import decrypt_git_config, encrypt_git_config, validate_git_config


def test_encrypt_decrypt_roundtrip():
    plaintext = {
        "repository": "https://github.com/test/repo.git",
        "username": "testuser",
        "token": "ghp_1234567890",
    }
    encrypted = encrypt_git_config(plaintext)
    expected_prefix = "DPAPI:v2:" if sys.platform == "win32" else "ENC:v1:"
    assert encrypted.startswith(expected_prefix)
    decrypted = decrypt_git_config(encrypted)
    assert decrypted == plaintext


def test_tampered_payload():
    plaintext = {"repository": "https://github.com/test/repo.git", "username": "test", "token": "abc"}
    encrypted = encrypt_git_config(plaintext)
    prefix, payload = encrypted.rsplit(":", 1)
    payload = payload[:-1] + ("A" if payload[-1] != "A" else "B")
    corrupt = f"{prefix}:{payload}"
    with pytest.raises(ValueError):
        decrypt_git_config(corrupt)


def test_invalid_version():
    with pytest.raises(ValueError):
        decrypt_git_config("ENC:v2:abc")


def test_validate():
    valid = {
        "repository_url": "https://github.com/test/repo.git",
        "username": "test",
        "token": "abc",
    }
    assert validate_git_config(valid) is True
    invalid = {"repository_url": "not-a-url", "username": "test"}
    assert validate_git_config(invalid) is False
