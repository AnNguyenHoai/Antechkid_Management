"""RV-02 additive schema compatibility / no-loss downgrade tests.

Legacy database content must survive the outbox schema migration unchanged;
downgrade cannot drop committed recovery history.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

MIGRATION = (
    Path(__file__).resolve().parents[1] / "migrations" / "versions"
    / "1e10a045_recovery_change_outbox.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location("rv02_outbox_migration_test", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_additive_outbox_migration_preserves_legacy_business_rows():
    engine = sa.create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as conn:
            conn.execute(sa.text("CREATE TABLE legacy_student (id INTEGER PRIMARY KEY, display TEXT)"))
            conn.execute(sa.text("INSERT INTO legacy_student VALUES (1, 'unchanged')"))
            migration = _migration()
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()
            # The outbox migration should not drop/alter any business table.
            assert conn.execute(sa.text("SELECT display FROM legacy_student WHERE id=1")).scalar_one() == "unchanged"
            assert "recovery_change_outbox" in sa.inspect(conn).get_table_names()
            indexes = {idx["name"] for idx in sa.inspect(conn).get_indexes("recovery_change_outbox")}
            assert {"ix_recovery_outbox_session", "ix_recovery_outbox_operation"} <= indexes
            operation_index = next(
                idx for idx in sa.inspect(conn).get_indexes("recovery_change_outbox")
                if idx["name"] == "ix_recovery_outbox_operation"
            )
            assert bool(operation_index["unique"]) is True
            # Explicitly safe to repeat in recovery tests without destroying rows.
            migration.upgrade()
            assert conn.execute(sa.text("SELECT COUNT(*) FROM legacy_student")).scalar_one() == 1
    finally:
        engine.dispose()


def test_downgrade_fails_closed_if_committed_recovery_history_exists():
    engine = sa.create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as conn:
            migration = _migration()
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()
            conn.execute(sa.text(
                "INSERT INTO recovery_change_outbox "
                "(event_id,operation_id,write_session_id,base_main_oid,"
                " occurred_at_utc,module,action,entity_type,summary_code,"
                " summary_args_json,schema_version) "
                "VALUES (:event,:operation,:session,:oid,"
                " '2026-11-05 00:00:00','student','CREATE','Student',"
                " 'student_CREATE','{}',1)"
            ), {
                "event": "00000000-0000-0000-0000-000000000001",
                "operation": "00000000-0000-0000-0000-000000000002",
                "session": "test-write",
                "oid": "a" * 40,
            })
            with pytest.raises(RuntimeError, match="preserve an encrypted backup"):
                migration.downgrade()
            assert conn.execute(sa.text("SELECT COUNT(*) FROM recovery_change_outbox")).scalar_one() == 1
    finally:
        engine.dispose()
