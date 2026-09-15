# -*- coding: utf-8 -*-
"""
Cryptography utilities for CenterManager.
Uses AES-256-GCM for authenticated encryption.
"""
import os
import json
import base64
import hashlib
from typing import Union, Dict, Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

import logging
logger = logging.getLogger(__name__)

_APPLICATION_KEY = b"CenterManager-Secret-Key-2026"
_KEY_SALT = b"CenterManager-Salt-2026"


def _derive_key() -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_KEY_SALT,
        iterations=100000,
        backend=default_backend(),
    )
    return kdf.derive(_APPLICATION_KEY)


def encrypt_git_config(plaintext: Union[str, dict]) -> str:
    if isinstance(plaintext, dict):
        plaintext = json.dumps(plaintext, ensure_ascii=False)

    key = _derive_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    payload = nonce + ciphertext
    b64_payload = base64.b64encode(payload).decode("ascii")
    return f"ENC:v1:{b64_payload}"


def decrypt_git_config(encrypted: str) -> dict:
    if not encrypted.startswith("ENC:v1:"):
        raise ValueError("Invalid encrypted format: must start with ENC:v1:")

    b64_payload = encrypted[7:]
    try:
        payload = base64.b64decode(b64_payload)
    except Exception as e:
        raise ValueError(f"Failed to decode base64: {e}")

    if len(payload) < 12:
        raise ValueError("Payload too short")
    nonce = payload[:12]
    ciphertext = payload[12:]

    key = _derive_key()
    aesgcm = AESGCM(key)

    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return json.loads(plaintext.decode("utf-8"))
    except Exception as e:
        raise ValueError(f"Decryption failed: {e}")


def validate_git_config(config: Dict[str, Any]) -> bool:
    """
    Validate Git configuration dictionary.
    Supports both 'repository' and 'repository_url' keys for backward compatibility.
    """
    # Normalize key
    if "repository" in config and "repository_url" not in config:
        config["repository_url"] = config["repository"]
    required = ["repository_url", "username", "token"]
    return all(key in config for key in required)