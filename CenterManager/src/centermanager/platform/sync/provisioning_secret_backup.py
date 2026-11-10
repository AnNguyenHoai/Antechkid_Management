"""Minimal, non-recursive preservation of workstation-bound credentials.

This is separate from advisory Recovery. Do not copy Recovery/captures,
SessionReports, or the Git worktree when provisioning a new workstation key.
The old encrypted DB/WAL remains untouched until the authenticated MAIN
installer moves it to startup-rollbacks.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from pathlib import Path


class ProvisioningEvidenceError(RuntimeError):
    pass


def preserve_provisioning_secrets(*, recovery_root: Path, key_bundle: Path,
                                  config_file: Path) -> Path | None:
    """Durably retain old machine-bound secrets before they may be replaced.

    Only small fixed paths are copied; no traversal into user files. The
    original bytes are never modified. Failure fails closed on credential
    replacement, not on the ordinary Git MAIN startup path.
    """
    sources = [("database-key.dpapi", Path(key_bundle)),
               ("config.json", Path(config_file))]
    existing = [(name, path) for name, path in sources if path.is_file()]
    if not existing:
        return None
    root = Path(recovery_root) / "provisioning-keys" / uuid.uuid4().hex
    try:
        root.mkdir(parents=True, exist_ok=False)
        for name, source in existing:
            if source.is_symlink():
                raise ProvisioningEvidenceError("Machine-bound secret is a symlink")
            target = root / name
            with source.open("rb") as reader, target.open("xb") as writer:
                sha_src = hashlib.sha256()
                for data in iter(lambda: reader.read(1024 * 1024), b""):
                    sha_src.update(data)
                    writer.write(data)
                writer.flush()
                os.fsync(writer.fileno())
            sha_dest = hashlib.sha256(target.read_bytes()).digest()
            if sha_src.digest() != sha_dest:
                raise ProvisioningEvidenceError("Machine-bound secret backup checksum mismatch")
        return root
    except (OSError, ProvisioningEvidenceError) as exc:
        raise ProvisioningEvidenceError(
            "Cannot preserve existing machine-bound credentials before re-provisioning"
        ) from exc
