"""Regression: colliding Alembic ID may be resolved only by CourseFee schema proof."""

import pytest
from sqlalchemy import create_engine, text

from centermanager.database.migration import (
    _BASELINE_TABLES,
    _POST_PRJ_REQUIRED_COLUMNS,
    _proven_legacy_coursefee_revision,
    assert_coursefee_database_lineage,
)


def _fixture(connection, *, income_index=True, expense_index=True, monthly=False):
    connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
    connection.execute(text("INSERT INTO alembic_version VALUES ('1e10a046')"))
    # Recreate the pre-CourseFee physical baseline without modifying a real DB.
    for table in sorted(_BASELINE_TABLES | set(_POST_PRJ_REQUIRED_COLUMNS)):
        if table in ("incomes", "expenses"):
            continue
        columns = _POST_PRJ_REQUIRED_COLUMNS.get(table, set())
        columns_sql = "".join(f", {column} TEXT" for column in sorted(columns))
        connection.execute(text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY{columns_sql})"))
    for table, with_index in (("incomes", income_index), ("expenses", expense_index)):
        extra = "".join(
            f", {column} TEXT" for column in sorted(
                _POST_PRJ_REQUIRED_COLUMNS.get(table, set())
            )
        )
        connection.execute(text(
            f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, idempotency_key TEXT{extra})"
        ))
        if with_index:
            connection.execute(text(
                f"CREATE UNIQUE INDEX ux_{table}_idempotency_key ON {table}(idempotency_key)"
            ))
    if monthly:
        connection.execute(text("CREATE TABLE monthly_tuition_plans (id INTEGER PRIMARY KEY)"))


def test_legacy_coursefee_is_identified_by_both_unique_submission_indexes():
    with create_engine("sqlite:///:memory:").begin() as connection:
        _fixture(connection)
        assert _proven_legacy_coursefee_revision(connection)
        assert_coursefee_database_lineage(connection)


@pytest.mark.parametrize("income_index,expense_index", [(False, True), (True, False), (False, False)])
def test_colliding_revision_without_full_coursefee_evidence_stays_rejected(income_index, expense_index):
    with create_engine("sqlite:///:memory:").begin() as connection:
        _fixture(connection, income_index=income_index, expense_index=expense_index)
        assert not _proven_legacy_coursefee_revision(connection)
        with pytest.raises(RuntimeError, match="Ambiguous Alembic revision"):
            assert_coursefee_database_lineage(connection)


def test_monthly_tuition_schema_is_rejected_even_when_indexes_are_forged():
    with create_engine("sqlite:///:memory:").begin() as connection:
        _fixture(connection, monthly=True)
        assert not _proven_legacy_coursefee_revision(connection)
        with pytest.raises(RuntimeError, match="Incompatible monthly-tuition database"):
            assert_coursefee_database_lineage(connection)


def test_revision_proof_does_not_change_database_metadata_during_readonly_check():
    with create_engine("sqlite:///:memory:").begin() as connection:
        _fixture(connection)
        assert_coursefee_database_lineage(connection)
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "1e10a046"
