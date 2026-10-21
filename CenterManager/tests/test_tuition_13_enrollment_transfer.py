from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.models.enrollment_transfer import EnrollmentTransfer
from centermanager.services.enrollment_transfer_service import (
    EnrollmentTransferService,
    EnrollmentTransferValidationError,
)


def _class(course_fee="1200000", planned_sessions=12):
    return SimpleNamespace(
        course_fee=Decimal(course_fee),
        planned_sessions=planned_sessions,
        has_course_contract=True,
    )


def test_target_contract_is_new_contract_and_supports_different_unit_fee():
    source_unit_fee = Decimal("100000.0000")
    contract = EnrollmentTransferService._target_contract(_class("2400000", 12), 7)

    assert contract["planned_sessions"] == 6
    assert contract["enrolled_from_session"] == 7
    assert contract["enrolled_until_session"] == 12
    assert contract["agreed_course_fee"] == Decimal("1200000.0000")
    assert contract["unit_fee"] == Decimal("200000.0000")
    assert contract["unit_fee"] != source_unit_fee


def test_transfer_reason_is_mandatory_before_storage_access():
    service = EnrollmentTransferService.__new__(EnrollmentTransferService)
    with pytest.raises(EnrollmentTransferValidationError, match="Transfer reason is required"):
        service._require_reason("  ")


def test_transfer_ledger_preserves_signed_source_balance_and_explicit_credit():
    transfer = EnrollmentTransfer(
        source_enrollment_id=10,
        target_enrollment_id=20,
        transferred_credit=Decimal("2100000.0000"),
        source_balance_before=Decimal("-2100000.0000"),
        reason="Move to advanced class",
    )
    assert transfer.source_enrollment_id == 10
    assert transfer.target_enrollment_id == 20
    assert transfer.transferred_credit == Decimal("2100000.0000")
    assert transfer.source_balance_before < 0


def test_migration_links_contracts_without_rewriting_history():
    root = Path(__file__).resolve().parents[1]
    migration = (root / "migrations/versions/1e10a035_enrollment_transfer.py").read_text(encoding="utf-8")

    assert 'revision = "1e10a035"' in migration
    assert 'down_revision = "1e10a034"' in migration
    assert '"enrollment_transfers"' in migration
    assert 'ForeignKey("enrollments.id", ondelete="RESTRICT")' in migration
    assert "transferred_credit >= 0" in migration
    assert "UPDATE incomes" not in migration
    assert "UPDATE sessions" not in migration
    assert "INSERT INTO enrollment_transfers" not in migration
    assert "FinancePeriod" not in migration


def test_service_is_atomic_audited_and_does_not_mutate_source_payments_or_sessions():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/centermanager/services/enrollment_transfer_service.py").read_text(encoding="utf-8")

    assert 'source.status = "WITHDRAWN"' in source
    assert 'target = Enrollment(' in source
    assert 'action="TUITION_ENROLLMENT_TRANSFER"' in source
    assert "session.commit()" in source
    assert "transferred_credit=credit" in source
    assert "credit > available_credit" in source
    assert "Resume the open tuition freeze before transferring" in source
    assert "Income(" not in source
    assert "Session.status" not in source
    assert "FinancePeriod" not in source
    assert "date.today" not in source


def test_outstanding_settlement_projects_credit_without_cash_income_rows():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/centermanager/repositories/income_repository.py").read_text(encoding="utf-8")

    assert "EnrollmentTransfer.target_enrollment_id == enrollment_id" in source
    assert "EnrollmentTransfer.source_enrollment_id == enrollment_id" in source
    assert "TuitionSettlementComponent.KIND_TRANSFER_IN" in source
    assert "TuitionSettlementComponent.KIND_TRANSFER_OUT" in source
    assert "amount=-self._decimal(transfer.transferred_credit)" in source
    assert "canonical settlement components" in source


def test_ui_requires_explicit_target_credit_and_reason():
    root = Path(__file__).resolve().parents[1]
    widget = (
        root / "src/centermanager/ui/student_workspace/enrollment_widget.py"
    ).read_text(encoding="utf-8")
    dialog = (
        root / "src/centermanager/ui/enrollment_transfer_dialog.py"
    ).read_text(encoding="utf-8")

    assert 'Button("Transfer class"' in widget
    assert "EnrollmentTransferService.from_enrollment_service" in widget
    assert "EnrollmentTransferDialog(" in widget
    assert "self._write_enabled and open_freeze is None" in widget

    assert "available_prepaid_credit" in dialog
    assert "transferred_credit=self.credit_input.value()" in dialog
    assert "A transfer reason is required." in dialog
    assert "Select target class" in dialog

def test_transfer_uses_same_exact_withdrawal_session_boundary_as_manual_withdraw():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "src/centermanager/services/enrollment_transfer_service.py"
    ).read_text(encoding="utf-8")

    resolver_at = source.index("EnrollmentService._resolve_withdrawn_from_session(")
    withdraw_at = source.index('source.status = "WITHDRAWN"')
    boundary_at = source.index(
        "source.withdrawn_from_session = source_withdrawn_from_session"
    )
    commit_at = source.index("session.commit()")

    assert resolver_at < withdraw_at < boundary_at < commit_at
    assert '"source_withdrawn_from_session": source_withdrawn_from_session' in source


def test_transfer_source_boundary_resolves_after_latest_completed_source_session():
    from datetime import date

    from centermanager.models.session import SessionStatus
    from centermanager.services.enrollment_service import EnrollmentService

    source_enrollment = SimpleNamespace(
        enrolled_from_session=1,
        enrolled_until_session=12,
    )
    source_sessions = [
        SimpleNamespace(session_number=8, status=SessionStatus.COMPLETED.value),
        SimpleNamespace(session_number=9, status=SessionStatus.COMPLETED.value),
        SimpleNamespace(session_number=10, status=SessionStatus.SCHEDULED.value),
        SimpleNamespace(session_number=11, status=SessionStatus.SCHEDULED.value),
    ]

    boundary = EnrollmentService._resolve_withdrawn_from_session(
        source_enrollment,
        source_sessions,
    )

    assert boundary == 10


def test_transfer_remains_single_commit_atomic_with_boundary_persistence():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "src/centermanager/services/enrollment_transfer_service.py"
    ).read_text(encoding="utf-8")
    transfer_body = source.split("def transfer(", 1)[1]

    assert transfer_body.count("session.commit()") == 1
    assert "source.withdrawn_from_session = source_withdrawn_from_session" in transfer_body
    assert transfer_body.index(
        "source.withdrawn_from_session = source_withdrawn_from_session"
    ) < transfer_body.index("session.commit()")

