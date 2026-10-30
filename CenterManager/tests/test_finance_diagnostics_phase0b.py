"""Phase 0B read-only attribution diagnostics against synthetic finance history."""
from datetime import date, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from centermanager.core.current_user import CurrentUserContext
from centermanager.database.base import Base
from centermanager.models import Class, Enrollment, Income, Student
from centermanager.services.finance_diagnostics_service import FinanceDiagnosticsService
from centermanager.services.permission_service import PermissionDeniedError


AS_OF = date(2026, 10, 30)
VIEWER = SimpleNamespace(role=SimpleNamespace(name="MANAGER"), permissions={"finance.view"})


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'diagnostics.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    yield factory, engine
    engine.dispose()


def _identity(factory, *, student_code="S1", class_name="Python", archived=False):
    with factory.begin() as session:
        student = Student(student_code=student_code, full_name="Synthetic Student",
                          status="ARCHIVED" if archived else "ACTIVE")
        class_ = Class(name=class_name, status="ARCHIVED" if archived else "ACTIVE",
                       deleted_at=datetime(2026, 10, 20) if archived else None)
        session.add_all([student, class_])
        session.flush()
        return student.id, class_.id


def _enrollment(factory, student_id, class_id, *, status="WITHDRAWN", canonical_id=None):
    with factory.begin() as session:
        row = Enrollment(student_id=student_id, class_id=class_id, status=status,
                         start_date=date(2026, 9, 1), end_date=date(2026, 10, 15),
                         reconciled_into_enrollment_id=canonical_id)
        session.add(row)
        session.flush()
        return row.id


def _income(factory, student_id, class_id, enrollment_id=None, *,
            status="ACTIVE", income_type="Tuition", deleted=False,
            payment_date=AS_OF, amount=875000):
    with factory.begin() as session:
        row = Income(student_id=student_id, class_id=class_id,
                     enrollment_id=enrollment_id, amount=amount,
                     income_type=income_type, payment_method="CASH",
                     payment_date=payment_date, status=status,
                     deleted_at=datetime(2026, 10, 20) if deleted else None)
        session.add(row)
        session.flush()
        return row.id


def _read(service, **kwargs):
    with CurrentUserContext(VIEWER):
        return service.get_findings(as_of_date=AS_OF, **kwargs)


def test_legacy_attribution_is_evidence_not_automatic_repair(db):
    factory, _ = db
    student_id, class_id = _identity(factory, archived=True)
    _enrollment(factory, student_id, class_id, status="WITHDRAWN")
    _enrollment(factory, student_id, class_id, status="COMPLETED")
    legacy_id = _income(factory, student_id, class_id)
    _income(factory, student_id, class_id, status="VOIDED")
    _income(factory, student_id, class_id, deleted=True)
    _income(factory, student_id, class_id, income_type="Book")
    _income(factory, student_id, class_id, payment_date=date(2026, 10, 31))

    page = _read(FinanceDiagnosticsService(factory))
    assert page.state == "OK" and page.error_code is None
    assert page.total_count == 1 and page.counts_by_rule == {"D01": 1, "D02": 0}
    finding, = page.findings
    assert finding.rule_id == "D01" and finding.entity_id == legacy_id
    assert finding.candidate_count == 2 and finding.enrollment_id is None
    assert "Synthetic Student" not in repr(page)


def test_linked_identity_and_reconciliation_lineage_with_legitimate_old_debt(db):
    factory, _ = db
    student_id, class_id = _identity(factory)
    other_student_id, other_class_id = _identity(factory, student_code="S2", class_name="Scratch")
    canonical = _enrollment(factory, student_id, class_id)
    old = _enrollment(factory, student_id, class_id, canonical_id=canonical)
    other = _enrollment(factory, other_student_id, other_class_id)
    _income(factory, student_id, class_id, canonical)  # Valid after withdrawal.
    mismatched = _income(factory, student_id, class_id, other)
    reconciled = _income(factory, student_id, class_id, old)

    page = _read(FinanceDiagnosticsService(factory), rule_id="D02", per_page=1)
    assert page.state == "OK" and page.total_count == 2
    assert [f.entity_id for f in page.findings] == [mismatched]
    assert page.findings[0].linked_student_id == other_student_id
    assert page.findings[0].linked_class_id == other_class_id
    second = _read(FinanceDiagnosticsService(factory), rule_id="D02", page=2, per_page=1)
    assert [f.entity_id for f in second.findings] == [reconciled]
    assert second.findings[0].canonical_enrollment_id == canonical


def test_no_candidate_and_missing_linked_enrollment_are_explicit(db):
    factory, _ = db
    student_id, class_id = _identity(factory)
    legacy = _income(factory, student_id, class_id)
    missing = _income(factory, student_id, class_id, enrollment_id=999)
    page = _read(FinanceDiagnosticsService(factory))
    assert [(f.rule_id, f.entity_id) for f in page.findings] == [
        ("D01", legacy), ("D02", missing),
    ]
    assert page.findings[0].candidate_count == 0
    assert page.findings[1].linked_student_id is None


def test_combined_pagination_empty_and_input_validation(db):
    factory, _ = db
    service = FinanceDiagnosticsService(factory)
    assert _read(service).state == "OK"
    assert _read(service).total_count == 0
    student_id, class_id = _identity(factory)
    canonical = _enrollment(factory, student_id, class_id)
    first = _income(factory, student_id, class_id)
    second = _income(factory, student_id, class_id, canonical)
    with factory.begin() as session:
        session.get(Enrollment, canonical).reconciled_into_enrollment_id = 999
    page1 = _read(service, per_page=1)
    page2 = _read(service, per_page=1, page=2)
    assert [(f.rule_id, f.entity_id) for f in page1.findings] == [("D01", first)]
    assert [(f.rule_id, f.entity_id) for f in page2.findings] == [("D02", second)]
    assert _read(service, page=3, per_page=1).findings == ()
    with CurrentUserContext(VIEWER):
        for kwargs in ({"rule_id": "D03"}, {"per_page": 101}, {"page": 0}):
            with pytest.raises(ValueError):
                service.get_findings(as_of_date=AS_OF, **kwargs)


def test_permission_failure_and_query_only_connection_restoration(db):
    factory, engine = db
    service = FinanceDiagnosticsService(factory)
    with CurrentUserContext(None), pytest.raises(PermissionDeniedError):
        service.get_findings(as_of_date=AS_OF)
    student_id, class_id = _identity(factory)
    income_id = _income(factory, student_id, class_id)
    with factory() as session:
        before = session.execute(select(Income.id, Income.amount, Income.enrollment_id)).all()
    statements = []

    def record(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        result = _read(service, rule_id="D01")
    finally:
        event.remove(engine, "before_cursor_execute", record)
    assert result.state == "OK" and result.findings[0].entity_id == income_id
    assert len(statements) <= 5  # PRAGMA ON/OFF + count + bounded page.
    with factory() as session:
        after = session.execute(select(Income.id, Income.amount, Income.enrollment_id)).all()
        assert session.connection().exec_driver_sql("PRAGMA query_only").scalar() == 0
    assert before == after


def test_failed_repository_read_is_error_and_does_not_poison_pool(db):
    factory, _ = db

    class BadProvider:
        def incomes(self, session):
            class BadRepo:
                def count_tuition_attribution_cases(self, *_):
                    session.connection().exec_driver_sql("CREATE TABLE forbidden_write (id INTEGER)")
            return BadRepo()

    result = _read(FinanceDiagnosticsService(factory, BadProvider()))
    assert result.state == "ERROR" and result.error_code == "DIAGNOSTICS_READ_FAILED"
    assert result.total_count is None and not result.findings
    with factory() as session:
        assert session.connection().exec_driver_sql("PRAGMA query_only").scalar() == 0
        tables = session.connection().exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE name = 'forbidden_write'"
        ).all()
    assert tables == []


def test_large_legacy_fixture_uses_bounded_sql_page(db):
    factory, engine = db
    student_id, class_id = _identity(factory)
    with factory.begin() as session:
        session.add_all([
            Income(student_id=student_id, class_id=class_id, amount=1000,
                   income_type="Tuition", payment_method="CASH", payment_date=AS_OF,
                   status="ACTIVE")
            for _ in range(250)
        ])
    statements = []

    def record(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        first = _read(FinanceDiagnosticsService(factory), per_page=100)
    finally:
        event.remove(engine, "before_cursor_execute", record)
    assert first.state == "OK" and first.total_count == 250
    assert len(first.findings) == 100
    assert len(statements) <= 5  # No per-finding query or unbounded ORM materialization.
    assert sum("LIMIT" in sql.upper() for sql in statements) == 1
