from datetime import date
from pathlib import Path
import pytest

from centermanager.services.expense_service import ExpenseService, ExpenseValidationError


def make_service():
    return ExpenseService.__new__(ExpenseService)


def test_expense_amount_must_be_positive():
    service = make_service()
    with pytest.raises(ExpenseValidationError):
        service._validate_amount(0)


def test_expense_payment_date_is_required():
    service = make_service()
    with pytest.raises(ExpenseValidationError):
        service._validate_payment_date(None)


def test_expense_payment_method_normalizes_legacy_values():
    service = make_service()
    assert service._validate_payment_method("TÀI KHOẢN CÁ NHÂN") == "CASH"
    assert service._validate_payment_method("TÀI KHOẢN CÔNG TY") == "BANK"
    assert service._validate_payment_method("Bank Transfer") == "BANK"


def test_expense_status_normalizes_legacy_values():
    service = make_service()
    assert service._validate_status("ĐÃ HOÀN TRẢ") == "Completed"
    assert service._validate_status("CHƯA HOÀN TRẢ") == "Pending"


def test_expense_lifecycle_has_soft_delete():
    source = Path("src/centermanager/services/expense_service.py").read_text(encoding="utf-8")
    repo = Path("src/centermanager/repositories/expense_repository.py").read_text(encoding="utf-8")
    assert "finance.expense.delete" in source
    assert "repo.soft_delete(expense)" in source
    assert "expense.deleted_at = datetime.now()" in repo


def test_expense_update_is_audited():
    source = Path("src/centermanager/services/expense_service.py").read_text(encoding="utf-8")
    assert 'event_type="ExpenseUpdated"' in source
    assert 'event_type="ExpenseDeleted"' in source


def test_expense_ui_projects_edit_delete_from_write_capability_and_period_state():
    source = Path("src/centermanager/ui/finance_workspace/expense_list_page.py").read_text(encoding="utf-8")
    assert "write_enabled=self._write_enabled" in source
    assert "domain_allowed=not self._period_closed" in source
    assert "edit_action.setEnabled(self._can(Capability.FINANCE_EXPENSE_UPDATE))" in source
    assert "delete_action.setEnabled(self._can(Capability.FINANCE_EXPENSE_DELETE))" in source


def test_expense_form_uses_canonical_payment_contract():
    source = Path("src/centermanager/ui/finance_workspace/expense_form_dialog.py").read_text(encoding="utf-8")
    assert 'addItem("Cash", "CASH")' in source
    assert 'addItem("Bank", "BANK")' in source
    assert 'addItem("Other", "Other")' not in source
    assert "currentData()" in source


def test_expense_form_uses_canonical_status_contract():
    source = Path("src/centermanager/ui/finance_workspace/expense_form_dialog.py").read_text(encoding="utf-8")
    assert '"Completed"' in source
    assert '"Pending"' in source
