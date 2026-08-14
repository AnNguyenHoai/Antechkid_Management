# -*- coding: utf-8 -*-
"""
Cryptography utilities for CenterManager.
Uses AES-256-GCM for authenticated encryption.
"""

import os
import json
import base64
import hashlib
from typing import Union

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

import logging
logger = logging.getLogger(__name__)

# Application symmetric key (derived from hardcoded passphrase)
# This protects against casual inspection, not reverse engineering.
_APPLICATION_KEY = b"CenterManager-Secret-Key-2026"
_KEY_SALT = b"CenterManager-Salt-2026"


def _derive_key() -> bytes:
    """Derive AES-256 key from passphrase."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_KEY_SALT,
        iterations=100000,
        backend=default_backend(),
    )
    return kdf.derive(_APPLICATION_KEY)


def encrypt_git_config(plaintext: Union[str, dict]) -> str:
    """
    Encrypt Git configuration using AES-256-GCM.
    Returns format: ENC:v1:<base64_payload>
    """
    if isinstance(plaintext, dict):
        plaintext = json.dumps(plaintext, ensure_ascii=False)

    key = _derive_key()
    aesgcm = AESGCM(key)

    # Generate 12-byte nonce
    nonce = os.urandom(12)

    # Encrypt
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

    # Combine nonce + ciphertext
    payload = nonce + ciphertext

    # Base64 encode
    b64_payload = base64.b64encode(payload).decode("ascii")

    return f"ENC:v1:{b64_payload}"


def decrypt_git_config(encrypted: str) -> str:
    """
    Decrypt Git configuration from ENC:v1 format.
    Returns plaintext JSON string.
    """
    if not encrypted.startswith("ENC:v1:"):
        raise ValueError("Invalid encrypted format: must start with ENC:v1:")

    # Remove prefix
    b64_payload = encrypted[7:]  # len("ENC:v1:") = 7

    # Decode base64
    try:
        payload = base64.b64decode(b64_payload)
    except Exception as e:
        raise ValueError(f"Failed to decode base64: {e}")

    # Extract nonce (first 12 bytes) and ciphertext
    if len(payload) < 12:
        raise ValueError("Payload too short")
    nonce = payload[:12]
    ciphertext = payload[12:]

    key = _derive_key()
    aesgcm = AESGCM(key)

    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")
    except Exception as e:
        raise ValueError(f"Decryption failed: {e}")