"""FIN-FIX-01: finance balance/Student profile same-source regressions.

Small synthetic SQLAlchemy fixture; no production database or Git repository.
"""
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from centermanager.database.base import Base
from centermanager.events.finance_events import FinanceDataChanged
from centermanager.models.income import Income
from centermanager.models.tuition_adjustment import TuitionAdjustment
from centermanager.repositories.income_repository import IncomeRepository
from centermanager.services.income_service import IncomeService, IncomeValidationError
from centermanager.services.outstanding_service import OutstandingService


@pytest.fixture
def session_factory(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "finance-fix.db"))
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _income(amount, *, enrollment_id=17, status=Income.STATUS_ACTIVE, deleted=False, income_id=None):
    return Income(
        id=income_id,
        student_id=11,
        class_id=13,
        enrollment_id=enrollment_id,
        amount=amount,
        income_type="Tuition",
        payment_method="CASH",
        payment_date=date(2026, 11, 1),
        status=status,
        deleted_at=datetime(2026, 11, 2) if deleted else None,
    )


def _credit(key):
    return TuitionAdjustment(
        enrollment_id=17,
        kind=TuitionAdjustment.KIND_CREDIT,
        amount=Decimal("300"),
        adjustment_date=date(2026, 11, 1),
        reason="synthetic discount",
        idempotency_key=key,
    )


def _income_service_for_session(session):
    service = IncomeService.__new__(IncomeService)
    service._repository_provider = SimpleNamespace(
        incomes=lambda _session: IncomeRepository(_session)
    )
    return service


def _paid_for_finance_and_student(session):
    provider = SimpleNamespace(incomes=lambda _session: IncomeRepository(session))
    service = OutstandingService.__new__(OutstandingService)
    service._repository_provider = provider
    direct = IncomeRepository(session).sum_active_tuition_for_enrollment(
        17, as_of_date=date(2026, 11, 6)
    )
    student_projection = service._get_total_paid(
        session, 17, as_of_date=date(2026, 11, 6)
    )
    assert direct == student_projection
    return direct


def test_void_and_soft_delete_income_recompute_same_canonical_course_balance(session_factory):
    with session_factory() as session:
        first = _income(400)
        second = _income(200)
        session.add_all([first, second])
        session.commit()
        assert _paid_for_finance_and_student(session) == 600
        assert 1000 - _paid_for_finance_and_student(session) == 400

        first.status = Income.STATUS_VOIDED
        session.commit()
        session.expire_all()
        assert _paid_for_finance_and_student(session) == 200
        assert 1000 - _paid_for_finance_and_student(session) == 800

        second.deleted_at = datetime(2026, 11, 6)
        session.commit()
        session.expire_all()
        assert _paid_for_finance_and_student(session) == 0
        assert 1000 - _paid_for_finance_and_student(session) == 1000


def test_immutable_payment_time_credit_blocks_void_edit_and_delete_until_reconciled(session_factory):
    with session_factory() as session:
        income = _income(400, income_id=100)
        session.add_all([income, _credit("tuition-payment-credit:income:100")])
        session.commit()
        with pytest.raises(IncomeValidationError, match="non-cash tuition credit"):
            _income_service_for_session(session)._ensure_payment_time_credit_not_orphaned(session, income)
        assert _paid_for_finance_and_student(session) == 700
        assert income.status == Income.STATUS_ACTIVE


def test_legacy_unattributed_payment_discount_fails_closed_not_silently_understates_debt(session_factory):
    with session_factory() as session:
        income = _income(400, income_id=101)
        session.add_all([income, _credit("tuition-payment-credit:legacy-uuid")])
        session.commit()
        with pytest.raises(IncomeValidationError, match="legacy payment-time credit"):
            _income_service_for_session(session)._ensure_payment_time_credit_not_orphaned(session, income)
        assert _paid_for_finance_and_student(session) == 700


def test_unrelated_income_is_not_blocked_by_another_explicitly_linked_credit(session_factory):
    with session_factory() as session:
        linked = _income(400, income_id=100)
        unrelated = _income(200, income_id=101)
        session.add_all([linked, unrelated, _credit("tuition-payment-credit:income:100")])
        session.commit()
        _income_service_for_session(session)._ensure_payment_time_credit_not_orphaned(session, unrelated)


def test_student_workspace_consumes_committed_finance_events_without_changing_data():
    from centermanager.ui.student_workspace.student_workspace_shell import StudentWorkspaceShell
    from PySide6.QtCore import QThread

    refreshed = []
    fake = SimpleNamespace(
        _current_student_id=19,
        detail_page=SimpleNamespace(
            financial_tab=SimpleNamespace(set_student=lambda student_id: refreshed.append(student_id))
        ),
        thread=lambda: QThread.currentThread(),
        _refresh_current_student_finance=lambda: refreshed.append(19),
    )
    StudentWorkspaceShell._on_finance_data_changed(
        fake, FinanceDataChanged(entity="income", action="voided", entity_id=9)
    )
    StudentWorkspaceShell._on_finance_data_changed(
        fake, FinanceDataChanged(entity="tuition_adjustment", action="credit_adjustment", entity_id=8)
    )
    assert refreshed == [19, 19]
    # Expense events must not refresh Student tuition; preserve both prior
    # refreshes (Income void + non-cash adjustment), not just the first.
    StudentWorkspaceShell._on_finance_data_changed(
        fake, FinanceDataChanged(entity="expense", action="deleted", entity_id=7)
    )
    assert refreshed == [19, 19]

    # Student Workspace may be open without a selected profile.
    fake._current_student_id = None
    StudentWorkspaceShell._on_finance_data_changed(
        fake, FinanceDataChanged(entity="income", action="deleted", entity_id=9)
    )
    assert refreshed == [19, 19]


def test_payment_time_credit_key_is_tied_to_exact_created_income():
    from pathlib import Path
    source = (
        Path(__file__).resolve().parents[1] / "src" / "centermanager" /
        "services" / "income_service.py"
    ).read_text(encoding="utf-8")
    assert 'idempotency_key=f"tuition-payment-credit:income:{income.id}"' in source
    assert source.count("self._ensure_payment_time_credit_not_orphaned(session, income)") == 3
