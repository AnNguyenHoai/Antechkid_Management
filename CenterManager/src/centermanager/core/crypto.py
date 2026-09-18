# -*- coding: utf-8 -*-
"""Cryptography compatibility boundary for Git configuration.

Windows production writes use DPAPI (v2).  The old AES-GCM v1 format is kept
only for backward-compatible reads and non-Windows development/tests so an
existing installation can migrate without losing its Git configuration.
"""
import os
import json
import base64
from typing import Union, Dict, Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

from centermanager.core.secret_store import protect_secret, unprotect_secret

# LEGACY READ COMPATIBILITY ONLY. Never use this application-wide key for new
# Windows production secrets. Existing ENC:v1 bundles are migrated to DPAPI:v2
# by GitConfigService after a successful load.
_LEGACY_APPLICATION_KEY = b"CenterManager-Secret-Key-2026"
_LEGACY_KEY_SALT = b"CenterManager-Salt-2026"


def _derive_legacy_key() -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_LEGACY_KEY_SALT,
        iterations=100000,
        backend=default_backend(),
    )
    return kdf.derive(_LEGACY_APPLICATION_KEY)


def _encrypt_legacy(plaintext: str) -> str:
    key = _derive_legacy_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return "ENC:v1:" + base64.b64encode(nonce + ciphertext).decode("ascii")


def encrypt_git_config(plaintext: Union[str, dict]) -> str:
    if isinstance(plaintext, dict):
        plaintext = json.dumps(plaintext, ensure_ascii=False)
    if os.name == "nt":
        return protect_secret(plaintext)
    # Linux/macOS are development/test platforms for the current Windows
    # prototype. Keeping v1 here preserves CI compatibility without weakening
    # the Windows production secret boundary.
    return _encrypt_legacy(plaintext)


def decrypt_git_config(encrypted: str) -> dict:
    if encrypted.startswith("DPAPI:v2:"):
        plaintext = unprotect_secret(encrypted)
        return json.loads(plaintext)

    if not encrypted.startswith("ENC:v1:"):
        raise ValueError("Invalid encrypted Git configuration format")

    try:
        payload = base64.b64decode(encrypted[7:])
    except Exception as exc:
        raise ValueError("Failed to decode legacy encrypted configuration") from exc
    if len(payload) < 12:
        raise ValueError("Legacy encrypted payload too short")

    nonce, ciphertext = payload[:12], payload[12:]
    try:
        plaintext = AESGCM(_derive_legacy_key()).decrypt(nonce, ciphertext, None)
        return json.loads(plaintext.decode("utf-8"))
    except Exception as exc:
        raise ValueError("Legacy Git configuration decryption failed") from exc


def validate_git_config(config: Dict[str, Any]) -> bool:
    if "repository" in config and "repository_url" not in config:
        config["repository_url"] = config["repository"]
    required = ["repository_url", "username", "token"]
    return all(key in config for key in required)
