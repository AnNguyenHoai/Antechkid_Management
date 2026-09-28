#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SEC-06 real-Windows production security UAT harness.

This tool is deliberately evidence-oriented.  It runs non-destructive checks
it can prove locally and prints MANUAL checks for scenarios that require a
second Windows profile/machine, the packaged application UI, Git publication,
or deliberate fault injection.

Run from an isolated production-UAT workspace, never against live center data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

CENTERMANAGER_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = CENTERMANAGER_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from centermanager.core.paths import get_paths
from centermanager.database.artifact_identity import (
    identity_manifest_path,
    validate_and_pin_identity,
)
from centermanager.database.artifact_security import validate_database_artifact
from centermanager.database.encryption import DatabaseKeyStore, is_plaintext_sqlite_file
from centermanager.database.engine import get_database_path


@dataclass
class Check:
    id: str
    status: str
    description: str
    evidence: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manual(check_id: str, description: str, evidence: str) -> Check:
    return Check(check_id, "MANUAL", description, evidence)


def run_checks() -> list[Check]:
    checks: list[Check] = []
    os.environ["ANTECHKIDS_DEPLOYMENT_PROFILE"] = "production"

    checks.append(Check(
        "SEC06-01",
        "PASS" if os.name == "nt" else "FAIL",
        "UAT is running on Windows.",
        f"platform={platform.platform()} os.name={os.name}",
    ))
    if os.name != "nt":
        return checks

    paths = get_paths()
    db_path = get_database_path()
    key_store = DatabaseKeyStore()

    checks.append(Check(
        "SEC06-02",
        "PASS" if db_path.is_file() else "FAIL",
        "Production runtime database exists.",
        str(db_path),
    ))
    checks.append(Check(
        "SEC06-03",
        "PASS" if key_store.bundle_path.is_file() else "FAIL",
        "DPAPI workspace-key bundle exists for this Windows profile.",
        str(key_store.bundle_path),
    ))
    if not db_path.is_file() or not key_store.bundle_path.is_file():
        return checks

    checks.append(Check(
        "SEC06-04",
        "FAIL" if is_plaintext_sqlite_file(db_path) else "PASS",
        "Production DB does not expose the plaintext SQLite header.",
        f"sha256={_sha256(db_path)}",
    ))

    try:
        key = key_store.load()
        checks.append(Check(
            "SEC06-05", "PASS", "DPAPI key unseals for the current Windows profile.",
            "DatabaseKeyStore.load() succeeded; raw key intentionally not printed.",
        ))
    except Exception as exc:
        checks.append(Check("SEC06-05", "FAIL", "DPAPI key unseals for the current Windows profile.", str(exc)))
        return checks

    try:
        validate_database_artifact(db_path, encryption_required=True, key=key)
        checks.append(Check(
            "SEC06-06", "PASS", "SQLCipher integrity/authentication validation succeeds.",
            "validate_database_artifact(encryption_required=True) succeeded.",
        ))
    except Exception as exc:
        checks.append(Check("SEC06-06", "FAIL", "SQLCipher integrity/authentication validation succeeds.", str(exc)))

    manifest = identity_manifest_path(db_path)
    checks.append(Check(
        "SEC06-07",
        "PASS" if manifest.is_file() else "FAIL",
        "Runtime/authoritative DB has a signed SEC-05 identity sidecar.",
        str(manifest),
    ))
    if manifest.is_file():
        try:
            identity = validate_and_pin_identity(db_path, key)
            checks.append(Check(
                "SEC06-08", "PASS", "Signed DB identity/hash/generation validates and pins.",
                f"database_id={identity.database_id} generation={identity.generation} sha256={identity.sha256}",
            ))
        except Exception as exc:
            checks.append(Check("SEC06-08", "FAIL", "Signed DB identity/hash/generation validates and pins.", str(exc)))

    checks.extend([
        _manual("SEC06-09", "Fresh default admin is forced to change password at first login.",
                "Launch packaged production build in isolated UAT workspace; capture login/change-password result."),
        _manual("SEC06-10", "Missing/wrong DPAPI workspace key fails closed without creating a replacement key.",
                "Temporarily move the UAT key bundle aside, launch packaged build, capture failure, then restore bundle."),
        _manual("SEC06-11", "Copied encrypted DB cannot be opened from another Windows profile/machine without provisioning the shared key.",
                "Copy only DB+identity to a clean Windows profile/machine and capture fail-closed startup."),
        _manual("SEC06-12", "Production backup is ciphertext and plaintext/wrong-key restore is rejected.",
                "Create UAT backup; inspect header; attempt controlled invalid restore and capture rejection."),
        _manual("SEC06-13", "Authorized encrypted backup restore succeeds and preserves application data.",
                "Create marker data, backup, mutate marker, restore with Admin+WRITE+reason+typed confirmation, verify marker."),
        _manual("SEC06-14", "Tampering one byte of a disposable DB copy is rejected by SEC-05 identity validation.",
                "Use a copied UAT DB+identity pair only; flip one byte and run startup/preflight."),
        _manual("SEC06-15", "Replacing DB+manifest with an older signed generation is rejected after a newer generation was pinned.",
                "Preserve two UAT generations, pin newer, then substitute older pair and capture rollback rejection."),
        _manual("SEC06-16", "Normal production Git pull/publish preserves DB identity and advances generation.",
                "Perform one isolated production-data-repository publish/pull cycle and record generation before/after."),
        _manual("SEC06-17", "Publication/restore failure does not leave split DB/identity/WAL/SHM state.",
                "Run the fault-injection regression suite or controlled disposable failure scenario; retain test/log evidence."),
    ])
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run SEC-06 Windows production security UAT checks.")
    parser.add_argument("--json", dest="json_path", help="Optional evidence JSON output path.")
    args = parser.parse_args(argv)

    checks = run_checks()
    for item in checks:
        print(f"[{item.status}] {item.id} - {item.description}")
        print(f"       {item.evidence}")

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "host": platform.node(),
        "platform": platform.platform(),
        "checks": [asdict(item) for item in checks],
    }
    if args.json_path:
        output = Path(args.json_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"[EVIDENCE] {output}")

    failed = [item for item in checks if item.status == "FAIL"]
    manual = [item for item in checks if item.status == "MANUAL"]
    print(f"SUMMARY: pass={sum(i.status == 'PASS' for i in checks)} fail={len(failed)} manual={len(manual)}")
    return 1 if failed else (2 if manual else 0)


if __name__ == "__main__":
    raise SystemExit(main())
