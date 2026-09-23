from datetime import date
from types import SimpleNamespace

from centermanager.ui.finance_workspace.expense_detail_dialog import ExpenseDetailDialog
from centermanager.ui.finance_workspace.expense_form_dialog import ExpenseFormDialog
from centermanager.ui.finance_workspace.finance_dashboard_page import FinanceDashboardPage


class _LegacyExpenseService:
    def __init__(self):
        self.updated = None

    def get_expense(self, _expense_id):
        return SimpleNamespace(
            id=7,
            category="Rent",
            description=None,
            amount=5_000_000.0,
            payment_method="Bank Transfer",
            payment_date=date(2026, 8, 31),
            paid_by=None,
            status="Paid",
            note=None,
        )

    def update_expense(self, **kwargs):
        self.updated = kwargs
        return self.get_expense(kwargs["expense_id"])


def test_expense_edit_preserves_unknown_legacy_category_and_null_description(qtbot):
    service = _LegacyExpenseService()
    dialog = ExpenseFormDialog(service, expense_id=7)
    qtbot.addWidget(dialog)

    assert dialog.category_combo.currentText() == "Rent"
    assert dialog.desc_edit.toPlainText() == ""
    assert dialog.method_combo.currentData() == "Bank"
    assert dialog.status_combo.currentData() == "Completed"

    dialog._save()

    assert service.updated is not None
    assert service.updated["category"] is None
    assert service.updated["description"] is None


def test_expense_detail_accepts_legacy_null_description(qtbot):
    dialog = ExpenseDetailDialog(_LegacyExpenseService(), 7)
    qtbot.addWidget(dialog)

    assert dialog.desc_label.text() == "-"
    assert dialog.category_label.text() == "Rent"


def test_finance_dashboard_accepts_legacy_null_expense_description(qtbot):
    page = FinanceDashboardPage(object())
    qtbot.addWidget(page)
    expense = SimpleNamespace(
        id=7,
        payment_date=date(2026, 8, 31),
        category="Rent",
        description=None,
        amount=5_000_000.0,
        status="Paid",
    )

    page._update_expense_table([expense])

    assert page._expense_ids == [7]
