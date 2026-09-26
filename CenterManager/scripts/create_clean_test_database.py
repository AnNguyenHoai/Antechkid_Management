#!/usr/bin/env python3
"""Create a schema-identical SQLite test database with no application data.

The source database is opened read-only and copied using SQLite's online backup
API so WAL-backed databases are snapshotted consistently. The destination copy
keeps schema objects and the Alembic revision row, removes all application-table
rows, resets AUTOINCREMENT state, then rewrites the file with VACUUM.

Run from CenterManager/:

    python scripts/create_clean_test_database.py

Optional:

    python scripts/create_clean_test_database.py \
        --source runtime/Database/center.db \
        --output runtime/Database/center.clean.db \
        --force
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Iterable


CENTER_MANAGER_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = CENTER_MANAGER_ROOT / "runtime" / "Database" / "center.db"
DEFAULT_OUTPUT = CENTER_MANAGER_ROOT / "runtime" / "Database" / "center.clean.db"
PRESERVED_TABLES = {"alembic_version"}


class CleanDatabaseError(RuntimeError):
    """Raised when a clean test database cannot be produced safely."""


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _read_only_uri(path: Path) -> str:
    # Path.as_uri() is portable for Windows drive letters and POSIX paths.
    return path.resolve().as_uri() + "?mode=ro"


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


def _trigger_definitions(connection: sqlite3.Connection) -> list[tuple[str, str]]:
    rows = connection.execute(
        """
        SELECT name, sql
        FROM sqlite_schema
        WHERE type = 'trigger'
          AND sql IS NOT NULL
        ORDER BY name
        """
    ).fetchall()
    return [(str(name), str(sql)) for name, sql in rows]


def _require_valid_source(source: Path) -> None:
    if not source.exists():
        raise CleanDatabaseError(f"Source database does not exist: {source}")
    if not source.is_file():
        raise CleanDatabaseError(f"Source database is not a file: {source}")

    try:
        with sqlite3.connect(_read_only_uri(source), uri=True) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise CleanDatabaseError(
                    f"Source database failed integrity_check: {integrity!r}"
                )
            tables = set(_user_tables(connection))
            if "alembic_version" not in tables:
                raise CleanDatabaseError(
                    "Source database has no alembic_version table; refusing to clone "
                    "an unknown or schema-empty SQLite file."
                )
    except sqlite3.DatabaseError as exc:
        raise CleanDatabaseError(f"Source is not a valid SQLite database: {source}") from exc


def _online_backup(source: Path, destination: Path) -> None:
    with sqlite3.connect(_read_only_uri(source), uri=True) as source_connection:
        with sqlite3.connect(destination) as destination_connection:
            source_connection.backup(destination_connection)


def _drop_triggers_temporarily(connection: sqlite3.Connection) -> list[tuple[str, str]]:
    definitions = _trigger_definitions(connection)
    for name, _sql in definitions:
        connection.execute(f"DROP TRIGGER {_quote_identifier(name)}")
    return definitions


def _restore_triggers(
    connection: sqlite3.Connection, definitions: Iterable[tuple[str, str]]
) -> None:
    for _name, sql in definitions:
        connection.execute(sql)


def _sanitize_database(path: Path) -> tuple[int, int]:
    """Delete all application rows while retaining schema and Alembic revision."""
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("PRAGMA secure_delete = ON")

        tables = _user_tables(connection)
        alembic_rows = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchall()
        if len(alembic_rows) != 1 or not alembic_rows[0][0]:
            raise CleanDatabaseError(
                "Expected exactly one non-empty alembic_version row in source snapshot."
            )

        trigger_definitions = _drop_triggers_temporarily(connection)
        deleted_tables = 0
        try:
            for table in tables:
                if table in PRESERVED_TABLES:
                    continue
                connection.execute(f"DELETE FROM {_quote_identifier(table)}")
                deleted_tables += 1

            # AUTOINCREMENT state is data, not schema. Reset it so IDs in a fresh
            # test database start from their normal initial values.
            sqlite_sequence_exists = connection.execute(
                "SELECT 1 FROM sqlite_schema "
                "WHERE type='table' AND name='sqlite_sequence'"
            ).fetchone()
            if sqlite_sequence_exists:
                connection.execute("DELETE FROM sqlite_sequence")

            _restore_triggers(connection, trigger_definitions)
            connection.commit()
        except Exception:
            connection.rollback()
            raise

        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise CleanDatabaseError(
                f"Sanitized database failed foreign_key_check: {violations[:5]!r}"
            )

        # VACUUM rewrites the file so deleted payload is not merely left behind
        # in reusable free pages.
        connection.execute("VACUUM")

        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise CleanDatabaseError(
                f"Sanitized database failed integrity_check: {integrity!r}"
            )

        remaining_rows = 0
        for table in tables:
            if table in PRESERVED_TABLES:
                continue
            count = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM {_quote_identifier(table)}"
                ).fetchone()[0]
            )
            remaining_rows += count

        if remaining_rows != 0:
            raise CleanDatabaseError(
                f"Sanitized database still contains {remaining_rows} application rows."
            )

        preserved_count = int(
            connection.execute("SELECT COUNT(*) FROM alembic_version").fetchone()[0]
        )
        if preserved_count != 1:
            raise CleanDatabaseError("alembic_version was not preserved correctly.")

        return deleted_tables, preserved_count


def create_clean_database(source: Path, output: Path, *, force: bool = False) -> None:
    source = source.expanduser().resolve()
    output = output.expanduser().resolve()

    _require_valid_source(source)
    if source == output:
        raise CleanDatabaseError("Output must be different from the source database.")
    if output.exists() and not force:
        raise CleanDatabaseError(
            f"Output already exists: {output}\nUse --force to replace it explicitly."
        )

    output.parent.mkdir(parents=True, exist_ok=True)

    temp_fd, temp_name = tempfile.mkstemp(
        prefix=f".{output.stem}.", suffix=".tmp.db", dir=output.parent
    )
    os.close(temp_fd)
    temp_path = Path(temp_name)

    try:
        _online_backup(source, temp_path)
        deleted_tables, preserved_count = _sanitize_database(temp_path)
        os.replace(temp_path, output)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    print("Clean test database created successfully.")
    print(f"  Source            : {source}")
    print(f"  Output            : {output}")
    print(f"  Cleared tables    : {deleted_tables}")
    print(f"  Application rows  : 0")
    print(f"  Preserved rows    : {preserved_count} (alembic_version only)")
    print("  SQLite integrity  : ok")
    print("  Foreign keys      : ok")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create a schema-identical CenterManager SQLite database with all "
            "application data removed."
        )
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help=f"Source SQLite database (default: {DEFAULT_SOURCE})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Clean database path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing output file. Never overwrites the source database.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    try:
        create_clean_database(args.source, args.output, force=args.force)
    except (CleanDatabaseError, sqlite3.DatabaseError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
