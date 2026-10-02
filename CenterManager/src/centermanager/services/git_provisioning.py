# -*- coding: utf-8 -*-
"""Destination-bound provisioning for Git credentials.

A destination installation owns an RSA private key protected by the local
Windows secret store (DPAPI). Only the public key leaves the destination. An
administrator encrypts Git configuration to that public key, producing a bundle
that can be transported safely but can only be opened by that installation.
"""

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from centermanager.core.secret_store import protect_secret, unprotect_secret

_REQUEST_FORMAT = "CenterManager-Git-Provisioning-Request:v1"
_BUNDLE_FORMAT = "CenterManager-Git-Provisioning-Bundle:v1"
_PRIVATE_KEY_FILE = "git_provisioning_private.json"


class ProvisioningError(ValueError):
    pass


@dataclass(frozen=True)
class ProvisioningPaths:
    private_key_file: Path


def _b64e(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _b64d(value: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except Exception as exc:
        raise ProvisioningError("Invalid provisioning base64 payload") from exc


def _paths(config_path: Path) -> ProvisioningPaths:
    return ProvisioningPaths(private_key_file=config_path.parent / _PRIVATE_KEY_FILE)


def ensure_destination_request(config_path: Path) -> Dict[str, Any]:
    """Return the destination public provisioning request, creating its key once."""
    paths = _paths(config_path)
    paths.private_key_file.parent.mkdir(parents=True, exist_ok=True)

    if paths.private_key_file.exists():
        record = json.loads(paths.private_key_file.read_text(encoding="utf-8"))
        public_pem = record.get("public_key")
        if isinstance(public_pem, str) and public_pem:
            return {"format": _REQUEST_FORMAT, "public_key": public_pem}

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")

    # The private key is never portable. On Windows it is bound to the current
    # Windows identity through DPAPI. Non-Windows is test/development only.
    if os.name == "nt":
        protected_private = protect_secret(private_pem)
    else:
        protected_private = "TEST:v1:" + _b64e(private_pem.encode("utf-8"))

    record = {
        "format": _REQUEST_FORMAT,
        "public_key": public_pem,
        "protected_private_key": protected_private,
    }
    paths.private_key_file.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return {"format": _REQUEST_FORMAT, "public_key": public_pem}


def write_destination_request(config_path: Path, output_path: Path) -> None:
    request = ensure_destination_request(config_path)
    output_path.write_text(json.dumps(request, indent=2), encoding="utf-8")


def create_bundle(request: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    """Encrypt a Git configuration payload to one destination public key."""
    if request.get("format") != _REQUEST_FORMAT:
        raise ProvisioningError("Unsupported provisioning request format")
    public_pem = request.get("public_key")
    if not isinstance(public_pem, str) or not public_pem:
        raise ProvisioningError("Provisioning request has no public key")

    try:
        public_key = serialization.load_pem_public_key(public_pem.encode("ascii"))
    except Exception as exc:
        raise ProvisioningError("Invalid destination public key") from exc

    aes_key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    plaintext = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ciphertext = AESGCM(aes_key).encrypt(nonce, plaintext, _BUNDLE_FORMAT.encode("ascii"))
    wrapped_key = public_key.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    return {
        "format": _BUNDLE_FORMAT,
        "wrapped_key": _b64e(wrapped_key),
        "nonce": _b64e(nonce),
        "ciphertext": _b64e(ciphertext),
    }


def decrypt_bundle(config_path: Path, bundle: Dict[str, Any]) -> Dict[str, Any]:
    """Open a bundle using only the destination's locally protected private key."""
    if bundle.get("format") != _BUNDLE_FORMAT:
        raise ProvisioningError("Unsupported provisioning bundle format")

    paths = _paths(config_path)
    if not paths.private_key_file.exists():
        raise ProvisioningError("This machine has no provisioning identity")
    record = json.loads(paths.private_key_file.read_text(encoding="utf-8"))
    protected_private = record.get("protected_private_key")
    if not isinstance(protected_private, str):
        raise ProvisioningError("Destination provisioning identity is invalid")

    try:
        if protected_private.startswith("DPAPI:v2:"):
            private_pem = unprotect_secret(protected_private)
        elif protected_private.startswith("TEST:v1:"):
            private_pem = _b64d(protected_private[8:]).decode("utf-8")
        else:
            raise ProvisioningError("Unsupported destination private-key protection")
        private_key = serialization.load_pem_private_key(
            private_pem.encode("ascii"), password=None
        )
        aes_key = private_key.decrypt(
            _b64d(bundle["wrapped_key"]),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        plaintext = AESGCM(aes_key).decrypt(
            _b64d(bundle["nonce"]),
            _b64d(bundle["ciphertext"]),
            _BUNDLE_FORMAT.encode("ascii"),
        )
        payload = json.loads(plaintext.decode("utf-8"))
    except ProvisioningError:
        raise
    except Exception as exc:
        raise ProvisioningError(
            "Provisioning bundle is invalid or belongs to another destination"
        ) from exc

    if not isinstance(payload, dict):
        raise ProvisioningError("Provisioning payload has invalid type")
    return payload
