"""Immutable local candidate storage adapter for isolated coordinator staging.

Production deployments must configure an externally durable, access-controlled object
store and signed-manifest validation; this module never decrypts SQLCipher.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import uuid

from .authority import CoordinatorError


class LocalCandidateStore:
    """Staging-only content-addressed storage (not a production HA backend)."""
    def __init__(self, root: Path):
        self.root = Path(root)

    def put(self, repository_id: str, payload: bytes, expected_sha256: str) -> str:
        digest = hashlib.sha256(payload).hexdigest()
        if digest != expected_sha256 or not payload:
            raise CoordinatorError("CANDIDATE_HASH_MISMATCH")
        if len(payload) > 256 * 1024 * 1024:
            raise CoordinatorError("CANDIDATE_TOO_LARGE")
        # Directory identity is derived from hash, not user-controlled path components.
        scope = hashlib.sha256(repository_id.encode()).hexdigest()
        destination = self.root / scope / digest
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                raise CoordinatorError("STORAGE_INTEGRITY_FAILURE")
            return digest
        temporary = destination.with_name("." + uuid.uuid4().hex + ".tmp")
        try:
            with temporary.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
            return digest
        finally:
            temporary.unlink(missing_ok=True)

    def verify(self, repository_id: str, sha256: str) -> bool:
        if len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256):
            return False
        scope = hashlib.sha256(repository_id.encode()).hexdigest()
        path = self.root / scope / sha256
        return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == sha256

    def size(self, repository_id: str, sha256: str) -> int:
        if not self.verify(repository_id, sha256):
            raise CoordinatorError("CANDIDATE_STORAGE_MISMATCH")
        scope = hashlib.sha256(repository_id.encode()).hexdigest()
        return (self.root / scope / sha256).stat().st_size

    def read(self, repository_id: str, sha256: str) -> bytes:
        """Return only bytes whose content-addressed hash still matches."""
        if not self.verify(repository_id, sha256):
            raise CoordinatorError("CANDIDATE_STORAGE_MISMATCH")
        scope = hashlib.sha256(repository_id.encode()).hexdigest()
        return (self.root / scope / sha256).read_bytes()
