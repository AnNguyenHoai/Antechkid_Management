"""REC-03: validate active MAIN generation independently from historic Recovery.

This contract does not grant WRITE. Live use must first activate an isolated
MAIN workspace through a crash-safe installer, and the existing remote lease,
fencing and CAS checks must still pass. Historic incidents are excluded from
this *identity* proof, not deleted or promoted to CLEAN.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path


class ActiveMainError(RuntimeError):
    pass


@dataclass(frozen=True)
class ActiveMainGeneration:
    commit_oid: str
    database_sha256: str
    database_path: Path


def verify_active_main_generation(stage, *, expected_main_oid: str) -> ActiveMainGeneration:
    """Prove the exact staged generation without consulting legacy case status.

    This is only an artifact proof; a newly activated workspace must also pass
    SQLCipher/schema checks and the independent distributed WRITE authority.
    """
    stage_path = Path(stage)
    if stage_path.is_symlink() or not stage_path.is_dir():
        raise ActiveMainError("Active MAIN stage is missing or a symlink.")
    proof = stage_path / "accepted-main.json"
    database = stage_path / "database" / "center.db"
    if proof.is_symlink() or database.is_symlink() or not proof.is_file() or not database.is_file():
        raise ActiveMainError("Active MAIN stage is incomplete.")
    try:
        document = json.loads(proof.read_text(encoding="utf-8"))
        accepted = document["accepted_main_oid"]
        hash_recorded = document["center_db_sha256"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ActiveMainError("Accepted MAIN stage receipt is malformed.") from exc
    if (document.get("format") != 1 or not isinstance(accepted, str)
            or not re.fullmatch(r"[a-fA-F0-9]{40,64}", accepted)
            or accepted != expected_main_oid
            or not isinstance(hash_recorded, str)
            or not re.fullmatch(r"[a-f0-9]{64}", hash_recorded)):
        raise ActiveMainError("Active MAIN commit/hash proof mismatch.")
    digest = hashlib.sha256()
    with database.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != hash_recorded:
        raise ActiveMainError("Active MAIN database differs from accepted receipt.")
    return ActiveMainGeneration(accepted, hash_recorded, database)
