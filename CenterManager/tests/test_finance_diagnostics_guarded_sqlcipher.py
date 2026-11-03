"""Regression: Finance Diagnostics must work on guarded SQLCipher in READ mode.

The existing diagnostics tests use unguarded SQLite; they cannot detect a
SQLITE_PRAGMA query_only rejection by GuardedConnection. This module uses
the disposable E1B-2A encrypted runtime with its actual local mutation gate.
No official Git MAIN, production key or deployed workspace is accessed.
"""
from datetime import date

import pytest

from tests.test_e1b1_durable_write_recovery import workspace  # noqa: F401 - reporting fixture dependency
from tests.test_e1b2a_post_publish_consistency import reporting  # noqa: F401
from centermanager.database.mutation_authority import MutationAuthorityError
from centermanager.repositories.income_repository import IncomeRepository
from centermanager.services.finance_diagnostics_service import FinanceDiagnosticsService


def test_finance_diagnostics_reads_real_guarded_sqlcipher_without_write(reporting):
    w = reporting
    assert not w.cm.is_writing()
    report = FinanceDiagnosticsService(w.factory).get_findings(
        as_of_date=date(2026, 11, 3),
    )
    assert report.state == "OK", report.error_code
    assert report.total_count == 0
    assert report.counts_by_rule == {"D01": 0, "D02": 0}
    assert report.findings == ()


def test_query_only_context_restores_connection_and_never_grants_write(reporting):
    w = reporting
    assert not w.cm.is_writing()
    with w.factory() as db:
        repo = IncomeRepository(db)
        connection = db.connection()
        assert connection.exec_driver_sql("PRAGMA query_only").scalar_one() == 0
        with repo.query_only():
            assert connection.exec_driver_sql("PRAGMA query_only").scalar_one() == 1
            assert db.execute(__import__("sqlalchemy").text("SELECT count(*) FROM incomes")).scalar_one() == 0
            with pytest.raises(Exception):
                connection.exec_driver_sql(
                    "INSERT INTO students (student_code, full_name, status) "
                    "VALUES ('NO_WRITE', 'Must not persist', 'ACTIVE')"
                )
        assert connection.exec_driver_sql("PRAGMA query_only").scalar_one() == 0
        with pytest.raises(MutationAuthorityError):
            connection.exec_driver_sql(
                "UPDATE students SET full_name='Not authorized' WHERE id=1"
            )
        with pytest.raises(MutationAuthorityError):
            connection.exec_driver_sql("PRAGMA journal_mode=DELETE")
        db.rollback()
    with w.factory() as db:
        student = db.execute(__import__("sqlalchemy").text("SELECT full_name FROM students WHERE id=1")).scalar_one()
        assert student == "Synthetic One"


def test_query_only_context_restores_after_diagnostic_query_error(reporting):
    w = reporting
    with w.factory() as db:
        repo = IncomeRepository(db)
        connection = db.connection()
        with pytest.raises(Exception):
            with repo.query_only():
                assert connection.exec_driver_sql("PRAGMA query_only").scalar_one() == 1
                connection.exec_driver_sql("SELECT * FROM diagnostics_table_does_not_exist")
        assert connection.exec_driver_sql("PRAGMA query_only").scalar_one() == 0
        db.rollback()
