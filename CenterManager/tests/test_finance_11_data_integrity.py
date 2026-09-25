from pathlib import Path

from centermanager.dto.outstanding_dto import (
    BALANCE_STATE_NO_TUITION_CONFIGURED,
    OutstandingDTO,
    OUTSTANDING_STATUS_NO_TUITION_CONFIGURED,
)


ROOT = Path(__file__).resolve().parents[1]
OUTSTANDING_SERVICE = ROOT / "src" / "centermanager" / "services" / "outstanding_service.py"
INCOME_REPOSITORY = ROOT / "src" / "centermanager" / "repositories" / "income_repository.py"


def test_missing_tuition_configuration_is_explicit():
    dto = OutstandingDTO.create(
        student_id=1, student_name="A", student_code="S1",
        class_id=10, class_name="Robotics",
        expected_tuition=0, paid=0, tuition_configured=False,
    )
    assert dto.status == OUTSTANDING_STATUS_NO_TUITION_CONFIGURED
    assert dto.balance_state == BALANCE_STATE_NO_TUITION_CONFIGURED
    assert dto.tuition_configured is False
    assert dto.outstanding == 0


def test_non_tuition_income_is_not_tuition_contract():
    outstanding_source = OUTSTANDING_SERVICE.read_text(encoding="utf-8")
    income_source = INCOME_REPOSITORY.read_text(encoding="utf-8")
    assert "sum_active_tuition_for_enrollment" in outstanding_source
    assert 'Income.income_type == "Tuition"' in income_source
    assert "Income.enrollment_id == enrollment_id" in income_source


def test_missing_fee_is_not_silently_skipped():
    source = OUTSTANDING_SERVICE.read_text(encoding="utf-8")
    assert "OUTSTANDING_STATUS_NO_TUITION_CONFIGURED" in source
    assert "tuition_configured=configured" in source
    assert "TuitionAccrualUnresolvedError" in source


def test_summary_excludes_unconfigured_fee_from_debt_math():
    source = OUTSTANDING_SERVICE.read_text(encoding="utf-8")
    assert "if dto.tuition_configured:" in source
    assert "has_unconfigured_tuition = True" in source
    assert "total_paid += self._amount(dto.paid)" in source


def test_outstanding_list_can_filter_configuration_problem():
    source = (ROOT / "src" / "centermanager" / "ui" / "finance_workspace" / "outstanding_list_page.py").read_text(encoding="utf-8")
    assert "BALANCE_STATE_NO_TUITION_CONFIGURED" in source
