from pathlib import Path

from centermanager.dto.outstanding_dto import OutstandingDTO


def test_configured_tuition_balance_contract():
    dto = OutstandingDTO.create(
        student_id=1, student_name="A", student_code="S1",
        class_id=10, class_name="Robotics",
        expected_tuition=1_000_000, paid=400_000,
    )
    assert dto.expected_tuition == 1_000_000
    assert dto.paid == 400_000
    assert dto.outstanding == 600_000
    assert dto.status == "Partial"


def test_overpayment_is_explicit_not_hidden():
    dto = OutstandingDTO.create(
        student_id=1, student_name="A", student_code="S1",
        class_id=10, class_name="Robotics",
        expected_tuition=1_000_000, paid=1_200_000,
    )
    assert dto.outstanding == -200_000
    assert dto.status == "Overpaid"


def test_unconfigured_fee_does_not_hide_real_payment():
    source = Path("src/centermanager/services/outstanding_service.py").read_text(encoding="utf-8")
    assert "total_paid += dto.paid" in source
    assert "if dto.tuition_configured:" in source
    assert "total_expected += dto.expected_tuition" in source


def test_student_summary_deduplicates_duplicate_enrollment_pairs():
    source = Path("src/centermanager/services/outstanding_service.py").read_text(encoding="utf-8")
    assert "seen_pairs = set()" in source
    assert "seen_class_ids = set()" in source


def test_student_financial_widget_uses_outstanding_source_of_truth():
    source = Path("src/centermanager/ui/student_workspace/student_financial_widget.py").read_text(encoding="utf-8")
    assert "OutstandingService" in source
    assert "get_student_summary" in source
    assert "self._summary.total_expected" in source
    assert "self._summary.total_paid" in source


def test_student_financial_widget_shows_per_class_status():
    source = Path("src/centermanager/ui/student_workspace/student_financial_widget.py").read_text(encoding="utf-8")
    assert '"Trạng thái"' in source
    assert "detail.status" in source
    assert '"Chưa cấu hình"' in source


def test_outstanding_list_does_not_display_unknown_debt_as_zero():
    source = Path("src/centermanager/ui/finance_workspace/outstanding_list_page.py").read_text(encoding="utf-8")
    assert '"Chưa xác định"' in source
    assert '"Chưa cấu hình"' in source
