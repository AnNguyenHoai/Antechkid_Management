"""Safely create and activate a clean CenterManager SQLite database.

The activation flow is intentionally conservative:
- requires explicit ``--yes`` confirmation;
- refuses an actively locked runtime database;
- checkpoints WAL and verifies no live ``-wal``/``-shm`` sidecars remain;
- creates and fully validates a clean candidate;
- creates a durable safety backup before promotion;
- atomically promotes the candidate when it is on the same filesystem;
- validates the promoted database and restores the original backup on failure.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from create_clean_test_database import create_clean_database


class ActivationError(RuntimeError):
    """Raised when clean-database activation cannot be completed safely."""


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _user_tables(connection: sqlite3.Connection) -> list[str]:
    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_schema
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    return [str(row[0]) for row in rows]


def _sidecar_paths(path: Path) -> tuple[Path, Path]:
    return Path(str(path) + "-wal"), Path(str(path) + "-shm")


def _validate_clean_database(path: Path) -> str:
    """Validate schema integrity and prove the candidate contains no app rows."""
    if not path.exists() or not path.is_file():
        raise ActivationError(f"Database does not exist: {path}")

    try:
        with sqlite3.connect(path) as conn:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise ActivationError(
                    f"Clean database integrity check failed: {integrity!r}"
                )

            fk_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
            if fk_errors:
                raise ActivationError(
                    f"Clean database foreign-key check failed: {fk_errors[:5]!r}"
                )

            tables = _user_tables(conn)
            if "alembic_version" not in tables:
                raise ActivationError("Clean database has no alembic_version table.")

            versions = conn.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchall()
            if len(versions) != 1 or not versions[0][0]:
                raise ActivationError(
                    "Clean database must contain exactly one non-empty Alembic revision."
                )

            remaining_rows = 0
            for table in tables:
                if table == "alembic_version":
                    continue
                remaining_rows += int(
                    conn.execute(
                        f"SELECT COUNT(*) FROM {_quote_identifier(table)}"
                    ).fetchone()[0]
                )
            if remaining_rows:
                raise ActivationError(
                    f"Clean database still contains {remaining_rows} application rows."
                )

            return str(versions[0][0])
    except sqlite3.DatabaseError as exc:
        raise ActivationError(f"Invalid SQLite database: {path}") from exc


def _prepare_source_for_activation(source: Path) -> None:
    """Fail closed when CenterManager or another writer still owns the database."""
    if not source.exists():
        raise FileNotFoundError(f"Runtime database does not exist: {source}")
    if not source.is_file():
        raise ActivationError(f"Runtime database is not a file: {source}")

    try:
        with sqlite3.connect(source, timeout=0, isolation_level=None) as conn:
            conn.execute("PRAGMA busy_timeout = 0")
            try:
                conn.execute("BEGIN EXCLUSIVE")
                conn.execute("ROLLBACK")
            except sqlite3.OperationalError as exc:
                raise ActivationError(
                    "Runtime database is busy. Close CenterManager and any SQLite "
                    "tools before activation."
                ) from exc

            # If the database uses WAL, flush all committed frames into the main
            # file before creating the safety backup or replacing the database.
            checkpoint = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            if checkpoint and int(checkpoint[0]) != 0:
                raise ActivationError(
                    "Could not checkpoint the runtime WAL. Close CenterManager "
                    "and retry activation."
                )
    except sqlite3.DatabaseError as exc:
        if isinstance(exc, ActivationError):
            raise
        raise ActivationError(f"Runtime database is not valid SQLite: {source}") from exc

    # When this process is the last SQLite connection, normal close removes WAL
    # sidecars. Persistent sidecars indicate another live connection or an unsafe
    # state; do not rename/replace the database underneath it.
    live_sidecars = [path for path in _sidecar_paths(source) if path.exists()]
    if live_sidecars:
        names = ", ".join(path.name for path in live_sidecars)
        raise ActivationError(
            f"Runtime SQLite sidecar(s) still active ({names}). Close CenterManager "
            "and retry."
        )


def _default_backup_path(source: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    candidate = source.with_name(
        f"{source.stem}.original-{stamp}{source.suffix}"
    )
    counter = 1
    while candidate.exists():
        candidate = source.with_name(
            f"{source.stem}.original-{stamp}-{counter}{source.suffix}"
        )
        counter += 1
    return candidate


def _atomic_copy(source: Path, destination: Path) -> None:
    """Copy into destination directory then atomically publish the completed file."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{destination.stem}.",
        suffix=".tmp.db",
        dir=destination.parent,
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        shutil.copy2(source, temp_path)
        # Windows can reject fsync() on a descriptor reopened read-only. Reopen
        # the fully-copied file read/write so the durability barrier remains
        # portable without weakening the atomic-publish contract.
        with temp_path.open("rb+") as handle:
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, destination)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def _restore_from_backup(backup: Path, source: Path) -> None:
    # Keep the backup as audit/recovery evidence even after rollback.
    _atomic_copy(backup, source)
    for sidecar in _sidecar_paths(source):
        sidecar.unlink(missing_ok=True)


def activate(
    source: Path,
    clean_copy: Path,
    backup: Path | None = None,
) -> tuple[Path, Path]:
    source = source.expanduser().resolve()
    clean_copy = clean_copy.expanduser().resolve()

    if source == clean_copy:
        raise ValueError("Clean-copy path must differ from the runtime database.")

    _prepare_source_for_activation(source)

    # Build from the current runtime DB using the existing online-backup/sanitize
    # implementation. Candidate creation never mutates the source.
    create_clean_database(source, clean_copy, force=True)
    candidate_revision = _validate_clean_database(clean_copy)

    # Candidate creation can take time. Recheck ownership/WAL immediately before
    # taking the safety backup and destructive promotion.
    _prepare_source_for_activation(source)

    if backup is None:
        backup = _default_backup_path(source)
    backup = backup.expanduser().resolve()
    if backup in {source, clean_copy}:
        raise ValueError("Backup path must differ from source and clean-copy paths.")
    if backup.exists():
        raise FileExistsError(f"Backup already exists: {backup}")

    _atomic_copy(source, backup)

    try:
        # os.replace is the final promotion primitive. With the default paths both
        # files are on the same filesystem, so replacement is atomic.
        os.replace(clean_copy, source)
        promoted_revision = _validate_clean_database(source)
        if promoted_revision != candidate_revision:
            raise ActivationError(
                "Promoted database Alembic revision changed during activation."
            )
    except Exception as exc:
        try:
            _restore_from_backup(backup, source)
        except Exception as restore_exc:
            raise ActivationError(
                "Activation failed and automatic rollback also failed. "
                f"Safety backup remains at {backup}. Rollback error: {restore_exc}"
            ) from exc
        raise ActivationError(
            f"Activation failed; original database restored from {backup}: {exc}"
        ) from exc

    for sidecar in _sidecar_paths(source):
        sidecar.unlink(missing_ok=True)

    return source, backup


def _build_parser() -> argparse.ArgumentParser:
    project_root = Path(__file__).resolve().parents[1]
    default_db = project_root / "runtime" / "Database" / "center.db"
    default_clean = project_root / "runtime" / "Database" / "center.clean.db"

    parser = argparse.ArgumentParser(
        description="Create and safely activate a clean CenterManager test database."
    )
    parser.add_argument("--source", type=Path, default=default_db)
    parser.add_argument("--clean-copy", type=Path, default=default_clean)
    parser.add_argument("--backup", type=Path, default=None)
    parser.add_argument(
        "--yes",
        action="store_true",
        help=(
            "Required confirmation: create a safety backup and replace the runtime "
            "database with a validated clean copy."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if not args.yes:
        print("Refusing to replace the runtime database without --yes.", file=sys.stderr)
        print("Close CenterManager, then run again with --yes.", file=sys.stderr)
        return 2

    try:
        active, backup = activate(args.source, args.clean_copy, args.backup)
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    print(f"[OK] Original DB safety backup: {backup}")
    print(f"[OK] Clean database activated: {active}")
    print("[OK] Integrity, foreign keys, Alembic revision and zero-row checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
