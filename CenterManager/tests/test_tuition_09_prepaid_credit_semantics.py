from decimal import Decimal
from pathlib import Path

from centermanager.dto.outstanding_dto import (
    BALANCE_STATE_NO_TUITION_CONFIGURED,
    BALANCE_STATE_OWED,
    BALANCE_STATE_PAID,
    BALANCE_STATE_PREPAID,
    OutstandingDTO,
)
from centermanager.services.outstanding_service import OutstandingService


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "src" / "centermanager" / "ui" / "finance_workspace" / "outstanding_list_page.py"
SERVICE = ROOT / "src" / "centermanager" / "services" / "outstanding_service.py"


def _dto(accrued, paid, *, configured=True):
    return OutstandingDTO.create(
        student_id=1,
        student_name="An",
        student_code="HS001",
        class_id=7,
        class_name="Python",
        expected_tuition=Decimal(str(accrued)),
        paid=Decimal(str(paid)),
        tuition_configured=configured,
        enrollment_id=99,
    )


def test_balance_state_owed_boundary():
    dto = _dto("1500000", "1200000")
    assert dto.outstanding == Decimal("300000")
    assert dto.debt_amount == Decimal("300000")
    assert dto.prepaid_amount == 0
    assert dto.balance_state == BALANCE_STATE_OWED


def test_balance_state_paid_boundary():
    dto = _dto("1500000", "1500000")
    assert dto.outstanding == 0
    assert dto.debt_amount == 0
    assert dto.prepaid_amount == 0
    assert dto.balance_state == BALANCE_STATE_PAID


def test_acceptance_prepaid_preserves_signed_balance():
    dto = _dto("1500000", "3600000")
    assert dto.outstanding == Decimal("-2100000")
    assert dto.debt_amount == 0
    assert dto.prepaid_amount == Decimal("2100000")
    assert dto.balance_state == BALANCE_STATE_PREPAID


def test_unresolved_contract_has_explicit_state_even_with_payment():
    dto = _dto("0", "500000", configured=False)
    assert dto.outstanding == Decimal("-500000")
    assert dto.balance_state == BALANCE_STATE_NO_TUITION_CONFIGURED


def test_kpis_never_net_prepaid_against_debt():
    owed = _dto("1500000", "1200000")
    prepaid = OutstandingDTO.create(
        student_id=2,
        student_name="Binh",
        student_code="HS002",
        class_id=8,
        class_name="Scratch",
        expected_tuition=Decimal("1500000"),
        paid=Decimal("3600000"),
        enrollment_id=100,
    )

    stats = OutstandingService._stats_for_rows([owed, prepaid])

    assert stats["total_outstanding"] == Decimal("300000")
    assert stats["total_prepaid"] == Decimal("2100000")
    assert stats["total_students_with_debt"] == 1
    assert stats["total_students_with_prepaid"] == 1


def test_read_model_and_ui_surface_canonical_prepaid_semantics():
    service_source = SERVICE.read_text(encoding="utf-8")
    page_source = PAGE.read_text(encoding="utf-8")

    assert '"total_prepaid"' in service_source
    assert '"Prepaid Credit"' in service_source
    assert '"Balance State"' in service_source
    assert "BALANCE_STATE_PREPAID" in page_source
    assert "self.prepaid_kpi" in page_source
    assert '"Trả trước / Dư"' in page_source
