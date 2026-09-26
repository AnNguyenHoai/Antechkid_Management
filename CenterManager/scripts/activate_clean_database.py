"""Activate a clean CenterManager SQLite database for manual testing.

This is a small wrapper around create_clean_test_database.py. It creates a clean
copy, backs up the current runtime database, and atomically promotes the clean
copy to the canonical center.db path.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from create_clean_test_database import create_clean_database


def _validate_clean_database(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise RuntimeError(f"Clean database integrity check failed: {integrity}")
        fk_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
        if fk_errors:
            raise RuntimeError(f"Clean database foreign-key check failed: {fk_errors[:5]}")


def activate(source: Path, clean_copy: Path, backup: Path | None = None) -> tuple[Path, Path]:
    source = source.resolve()
    clean_copy = clean_copy.resolve()
    if not source.exists():
        raise FileNotFoundError(f"Runtime database does not exist: {source}")
    if source == clean_copy:
        raise ValueError("Clean-copy path must differ from the runtime database.")

    create_clean_database(source, clean_copy, force=True)
    _validate_clean_database(clean_copy)

    if backup is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = source.with_name(f"{source.stem}.original-{stamp}{source.suffix}")
    backup = backup.resolve()
    if backup in {source, clean_copy}:
        raise ValueError("Backup path must differ from source and clean-copy paths.")
    if backup.exists():
        raise FileExistsError(f"Backup already exists: {backup}")

    # os.replace keeps activation atomic on the same filesystem. The original
    # database is preserved first; if clean promotion fails, restore it.
    os.replace(source, backup)
    try:
        os.replace(clean_copy, source)
    except Exception:
        os.replace(backup, source)
        raise

    _validate_clean_database(source)
    return source, backup


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    default_db = project_root / "runtime" / "Database" / "center.db"
    default_clean = project_root / "runtime" / "Database" / "center.clean.db"

    parser = argparse.ArgumentParser(description="Create and activate a clean CenterManager test database.")
    parser.add_argument("--source", type=Path, default=default_db)
    parser.add_argument("--clean-copy", type=Path, default=default_clean)
    parser.add_argument("--backup", type=Path, default=None)
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required confirmation: back up the current runtime DB and replace it with the clean copy.",
    )
    args = parser.parse_args()

    if not args.yes:
        print("Refusing to replace the runtime database without --yes.", file=sys.stderr)
        print("Run again with --yes after closing CenterManager.", file=sys.stderr)
        return 2

    try:
        active, backup = activate(args.source, args.clean_copy, args.backup)
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    print(f"[OK] Original DB backed up: {backup}")
    print(f"[OK] Clean database activated: {active}")
    print("[OK] Integrity/FK validation passed. Open CenterManager normally for clean-data testing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
