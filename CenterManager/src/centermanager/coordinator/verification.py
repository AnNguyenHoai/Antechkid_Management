"""Trusted signed candidate verification boundary for E1C staging.

A signer must be provisioned out-of-band and its public key pinned per repository.
Neither uploader identity nor untrusted manifest data grants signing authority.
"""
import base64
import hashlib
import json
from dataclasses import dataclass
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

from .authority import CoordinatorError


def canonical_manifest(manifest):
    required = {"protocol", "repository_id", "database_id", "generation",
                "ciphertext_sha256", "ciphertext_size"}
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise CoordinatorError("INVALID_MANIFEST")
    if (manifest["protocol"] != "e1c-candidate-v1"
            or any(not isinstance(manifest[k], str) or not manifest[k]
                   for k in ("repository_id", "database_id"))
            or type(manifest["generation"]) is not int or manifest["generation"] < 1
            or type(manifest["ciphertext_size"]) is not int or manifest["ciphertext_size"] <= 0):
        raise CoordinatorError("INVALID_MANIFEST")
    digest = manifest["ciphertext_sha256"]
    if not isinstance(digest, str) or len(digest) != 64 or any(x not in "0123456789abcdef" for x in digest):
        raise CoordinatorError("INVALID_MANIFEST")
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


@dataclass(frozen=True)
class TrustedRepository:
    database_id: str
    signer_public_key: bytes


class CandidateVerifier:
    """Never accepts unsigned or untrusted-signature ciphertext as verified."""
    def __init__(self, authority, store, trusted_repositories):
        self.authority = authority
        self.store = store
        self.trusted = dict(trusted_repositories)

    def verify_and_register(self, repo_id, principal, candidate_id, manifest, signature_b64):
        trusted = self.trusted.get(repo_id)
        if trusted is None:
            raise CoordinatorError("UNKNOWN_TRUST_ROOT")
        payload = canonical_manifest(manifest)
        if manifest["repository_id"] != repo_id or manifest["database_id"] != trusted.database_id:
            raise CoordinatorError("DATABASE_IDENTITY_MISMATCH")
        try:
            signature = base64.b64decode(signature_b64, validate=True)
            Ed25519PublicKey.from_public_bytes(trusted.signer_public_key).verify(signature, payload)
        except (ValueError, InvalidSignature, TypeError) as exc:
            raise CoordinatorError("INVALID_SIGNATURE") from exc
        sha = manifest["ciphertext_sha256"]
        if not self.store.verify(repo_id, sha):
            raise CoordinatorError("CANDIDATE_STORAGE_MISMATCH")
        if self.store.size(repo_id, sha) != manifest["ciphertext_size"]:
            raise CoordinatorError("CANDIDATE_SIZE_MISMATCH")
        state = self.authority.state(repo_id)
        if manifest["generation"] <= state["generation"]:
            raise CoordinatorError("STALE_GENERATION")
        self.authority.register_candidate(
            repo_id, principal, candidate_id, sha, manifest["generation"],
            trusted.database_id, verified=True
        )
        return {"status": "VERIFIED_CANDIDATE", "candidate_id": candidate_id,
                "ciphertext_sha256": sha, "generation": manifest["generation"]}
