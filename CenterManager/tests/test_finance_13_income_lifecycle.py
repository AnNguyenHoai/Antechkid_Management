from datetime import date
from pathlib import Path

import pytest

from centermanager.services.income_service import IncomeService, IncomeValidationError


def make_service():
    return IncomeService.__new__(IncomeService)


def test_tuition_requires_student_and_class():
    service = make_service()
    with pytest.raises(IncomeValidationError):
        service._validate_income_ownership("Tuition", None, None)


def test_student_income_rejects_partial_ownership():
    service = make_service()
    with pytest.raises(IncomeValidationError):
        service._validate_income_ownership("Book", 1, None)


def test_other_income_must_not_be_student_linked():
    service = make_service()
    with pytest.raises(IncomeValidationError):
        service._validate_income_ownership("Other", 1, 10)


def test_other_income_is_valid_without_student():
    service = make_service()
    service._validate_income_ownership("Other", None, None)


def test_income_update_supports_received_by():
    source = Path("src/centermanager/services/income_service.py").read_text(encoding="utf-8")
    assert "received_by: Optional[str] = None" in source
    assert "income.received_by = new_received_by" in source


def test_income_form_passes_received_by_on_edit():
    source = Path("src/centermanager/ui/finance_workspace/income_form_dialog.py").read_text(encoding="utf-8")
    assert "received_by=received_by" in source


def test_income_form_locks_source_by_income_type():
    source = Path("src/centermanager/ui/finance_workspace/income_form_dialog.py").read_text(encoding="utf-8")
    assert "def _on_income_type_changed" in source
    assert 'if income_type == "Other"' in source


def test_income_ui_disables_edit_delete_without_write():
    source = Path("src/centermanager/ui/finance_workspace/income_list_page.py").read_text(encoding="utf-8")
    assert "edit_action.setEnabled(self._write_enabled)" in source
    assert "delete_action.setEnabled(self._write_enabled)" in source


def test_app_constructs_outstanding_before_dashboard():
    source = Path("src/centermanager/app.py").read_text(encoding="utf-8")
    assert source.index("outstanding_service = OutstandingService(session_factory)") < source.index("finance_dashboard_service = FinanceDashboardService(")
