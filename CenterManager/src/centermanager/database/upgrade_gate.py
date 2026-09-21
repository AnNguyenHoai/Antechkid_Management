# -*- coding: utf-8 -*-
"""Pre-release upgrade gate for a production-like SQLite database copy."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable

from centermanager.database.migration import (
    get_current_revision,
    get_head_revision,
    upgrade_database_path_to_head,
)

_IGNORED_COUNT_TABLES = {"alembic_version", "sqlite_sequence"}


class DatabaseUpgradeGateError(RuntimeError):
    """Raised when a production database upgrade rehearsal is unsafe or invalid."""


@dataclass(frozen=True)
class DatabaseHealth:
    integrity_check: str
    foreign_key_violations: int
    table_counts: Dict[str, int]


@dataclass(frozen=True)
class DatabaseUpgradeGateReport:
    status: str
    source_database: str
    snapshot_database: str
    snapshot_sha256_before_upgrade: str
    source_revision: str | None
    target_revision: str
    upgraded_revision: str | None
    integrity_before: str
    integrity_after: str
    foreign_key_violations_before: int
    foreign_key_violations_after: int
    table_counts_before: Dict[str, int]
    table_counts_after: Dict[str, int]
    completed_at_utc: str


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _connect_read_only(database_path: Path) -> sqlite3.Connection:
    uri = f"file:{database_path.resolve().as_posix()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _user_tables(connection: sqlite3.Connection) -> Iterable[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return (row[0] for row in rows)


def inspect_database_health(database_path: Path) -> DatabaseHealth:
    """Read integrity, foreign-key state, and row counts without mutating the DB."""
    database_path = Path(database_path)
    if not database_path.exists() or not database_path.is_file():
        raise DatabaseUpgradeGateError(f"Database file does not exist: {database_path}")
    if database_path.stat().st_size == 0:
        raise DatabaseUpgradeGateError(f"Database file is empty: {database_path}")

    try:
        connection = _connect_read_only(database_path)
        try:
            integrity_rows = connection.execute("PRAGMA integrity_check").fetchall()
            integrity = "\n".join(str(row[0]) for row in integrity_rows)
            fk_violations = connection.execute("PRAGMA foreign_key_check").fetchall()
            counts: Dict[str, int] = {}
            for table in _user_tables(connection):
                if table in _IGNORED_COUNT_TABLES:
                    continue
                row = connection.execute(
                    f"SELECT COUNT(*) FROM {_quote_identifier(table)}"
                ).fetchone()
                counts[table] = int(row[0])
        finally:
            connection.close()
    except sqlite3.DatabaseError as exc:
        raise DatabaseUpgradeGateError(
            f"Could not inspect SQLite database {database_path}: {exc}"
        ) from exc

    return DatabaseHealth(
        integrity_check=integrity,
        foreign_key_violations=len(fk_violations),
        table_counts=counts,
    )


def assert_healthy(health: DatabaseHealth, *, phase: str) -> None:
    if health.integrity_check.strip().lower() != "ok":
        raise DatabaseUpgradeGateError(
            f"{phase}: PRAGMA integrity_check failed: {health.integrity_check}"
        )
    if health.foreign_key_violations:
        raise DatabaseUpgradeGateError(
            f"{phase}: {health.foreign_key_violations} foreign-key violation(s) detected"
        )


def create_consistent_snapshot(source_database: Path, snapshot_database: Path) -> None:
    """Create a transactionally consistent SQLite snapshot without writing source."""
    source_database = Path(source_database).resolve()
    snapshot_database = Path(snapshot_database).resolve()
    if source_database == snapshot_database:
        raise DatabaseUpgradeGateError("Snapshot path must differ from the source database")
    if not source_database.exists() or not source_database.is_file():
        raise DatabaseUpgradeGateError(f"Source database does not exist: {source_database}")

    snapshot_database.parent.mkdir(parents=True, exist_ok=True)
    if snapshot_database.exists():
        raise DatabaseUpgradeGateError(
            f"Refusing to overwrite existing snapshot: {snapshot_database}"
        )

    source = _connect_read_only(source_database)
    destination = sqlite3.connect(snapshot_database)
    try:
        source.backup(destination)
        destination.commit()
    finally:
        destination.close()
        source.close()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_preserved_rows(before: Dict[str, int], after: Dict[str, int]) -> None:
    """Fail closed if any table that existed before migration loses/changes rows."""
    missing = sorted(set(before) - set(after))
    changed = {
        table: (before[table], after[table])
        for table in sorted(set(before) & set(after))
        if before[table] != after[table]
    }
    if missing or changed:
        details = []
        if missing:
            details.append(f"missing tables={missing}")
        if changed:
            details.append(f"row-count changes={changed}")
        raise DatabaseUpgradeGateError(
            "Migration changed pre-existing business data; explicit migration review is required: "
            + "; ".join(details)
        )


def run_database_upgrade_gate(
    source_database: Path,
    evidence_dir: Path,
) -> DatabaseUpgradeGateReport:
    """Rehearse the release migration on a consistent copy and prove invariants."""
    source_database = Path(source_database).resolve()
    evidence_dir = Path(evidence_dir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    snapshot_database = evidence_dir / "center.upgrade-rehearsal.db"
    report_path = evidence_dir / "database-upgrade-report.json"

    create_consistent_snapshot(source_database, snapshot_database)
    snapshot_hash = sha256_file(snapshot_database)

    before = inspect_database_health(snapshot_database)
    assert_healthy(before, phase="pre-upgrade")
    source_revision = get_current_revision(snapshot_database)
    target_revision = get_head_revision(snapshot_database)

    upgrade_database_path_to_head(snapshot_database)

    after = inspect_database_health(snapshot_database)
    assert_healthy(after, phase="post-upgrade")
    upgraded_revision = get_current_revision(snapshot_database)
    if upgraded_revision != target_revision:
        raise DatabaseUpgradeGateError(
            f"Database is not at Alembic head after upgrade: "
            f"current={upgraded_revision!r}, head={target_revision!r}"
        )
    assert_preserved_rows(before.table_counts, after.table_counts)

    report = DatabaseUpgradeGateReport(
        status="passed",
        source_database=str(source_database),
        snapshot_database=str(snapshot_database),
        snapshot_sha256_before_upgrade=snapshot_hash,
        source_revision=source_revision,
        target_revision=target_revision,
        upgraded_revision=upgraded_revision,
        integrity_before=before.integrity_check,
        integrity_after=after.integrity_check,
        foreign_key_violations_before=before.foreign_key_violations,
        foreign_key_violations_after=after.foreign_key_violations,
        table_counts_before=before.table_counts,
        table_counts_after=after.table_counts,
        completed_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    report_path.write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report
