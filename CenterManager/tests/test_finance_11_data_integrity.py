from centermanager.dto.outstanding_dto import (
    OutstandingDTO,
    OUTSTANDING_STATUS_NO_TUITION_CONFIGURED,
)


def test_missing_tuition_configuration_is_explicit():
    dto = OutstandingDTO.create(
        student_id=1, student_name="A", student_code="S1",
        class_id=10, class_name="Robotics",
        expected_tuition=0, paid=0, tuition_configured=False,
    )
    assert dto.status == OUTSTANDING_STATUS_NO_TUITION_CONFIGURED
    assert dto.tuition_configured is False
    assert dto.outstanding == 0


def test_non_tuition_income_is_not_tuition_contract():
    from pathlib import Path
    source = Path("src/centermanager/services/outstanding_service.py").read_text(encoding="utf-8")
    assert 'TUITION_INCOME_TYPE = "Tuition"' in source
    assert 'income_type=self.TUITION_INCOME_TYPE' in source


def test_missing_fee_is_not_silently_skipped():
    from pathlib import Path
    source = Path("src/centermanager/services/outstanding_service.py").read_text(encoding="utf-8")
    assert 'OUTSTANDING_STATUS_NO_TUITION_CONFIGURED' in source
    assert 'tuition_configured=configured' in source
    assert 'skip' not in source.lower() or 'skipped' not in source.lower()


def test_summary_excludes_unconfigured_fee_from_debt_math():
    from pathlib import Path
    source = Path("src/centermanager/services/outstanding_service.py").read_text(encoding="utf-8")
    assert 'if dto.tuition_configured:' in source
    assert 'has_unconfigured_tuition = True' in source


def test_outstanding_list_can_filter_configuration_problem():
    from pathlib import Path
    source = Path("src/centermanager/ui/finance_workspace/outstanding_list_page.py").read_text(encoding="utf-8")
    assert '"No Tuition Configured"' in source
