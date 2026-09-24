from datetime import date
from types import SimpleNamespace

from centermanager.core.current_user import CurrentUserContext
from centermanager.models.finance_period import ResolvedFinancePeriod
from centermanager.services.finance_period_service import FinancePeriodService
from centermanager.ui.finance_workspace.expense_form_dialog import ExpenseFormDialog
from centermanager.ui.finance_workspace.finance_workspace_shell import FinanceWorkspaceShell
from centermanager.ui.finance_workspace.income_form_dialog import IncomeFormDialog


class _EmptyStudentService:
    def list_students(self):
        return []


class _EmptyClassService:
    def list_classes(self):
        return []


class _ExpenseReadService:
    def __init__(self, payment_method="Bank", status="Pending"):
        self._payment_method = payment_method
        self._status = status

    def get_expense(self, _expense_id):
        return SimpleNamespace(
            category="Office Rent",
            description="September rent",
            amount=5_000_000.0,
            payment_method=self._payment_method,
            payment_date=date(2026, 9, 20),
            paid_by="Admin",
            status=self._status,
            note="Keep canonical values",
        )


class _FinanceViewer:
    is_admin = False
    is_active = True
    role = SimpleNamespace(name="finance")

    def has_permission(self, permission_name):
        return permission_name == "finance.view"


class _SessionContext:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, tb):
        return False


class _FinancePeriodRepo:
    def __init__(self, period):
        self._period = period

    def get_effective(self, _target):
        return self._period


class _RepositoryProvider:
    def __init__(self, period):
        self._period = period

    def finance_periods(self, _session):
        return _FinancePeriodRepo(self._period)


def test_finance_viewer_can_resolve_active_period_without_admin_period_capability():
    period = SimpleNamespace(effective_from=date(2026, 9, 15), duration_months=1)
    service = FinancePeriodService(
        lambda: _SessionContext(),
        repository_provider=_RepositoryProvider(period),
    )
    with CurrentUserContext(_FinanceViewer()):
        assert service.get_active_period(date(2026, 9, 23)) is period


def test_current_canonical_period_targets_business_date():
    today = date(2026, 9, 23)
    period = ResolvedFinancePeriod(
        configuration_id=1,
        period_start=date(2026, 9, 15),
        period_end=date(2026, 10, 14),
    )
    assert FinanceWorkspaceShell._target_date_for_period(period, today) == today


def test_historical_canonical_period_targets_exact_period_start():
    today = date(2026, 9, 23)
    period = ResolvedFinancePeriod(
        configuration_id=1,
        period_start=date(2026, 7, 15),
        period_end=date(2026, 8, 14),
    )
    assert FinanceWorkspaceShell._target_date_for_period(period, today) == date(
        2026, 7, 15
    )


def test_income_create_form_accepts_selected_period_initial_date(qtbot):
    dialog = IncomeFormDialog(
        object(),
        _EmptyStudentService(),
        _EmptyClassService(),
        initial_payment_date=date(2026, 8, 31),
    )
    qtbot.addWidget(dialog)
    assert dialog.date_edit.date().toPython() == date(2026, 8, 31)


def test_expense_create_form_accepts_selected_period_initial_date(qtbot):
    dialog = ExpenseFormDialog(
        object(),
        initial_payment_date=date(2026, 8, 31),
    )
    qtbot.addWidget(dialog)
    assert dialog.date_edit.date().toPython() == date(2026, 8, 31)


def test_expense_edit_restores_canonical_bank_and_pending_values(qtbot):
    dialog = ExpenseFormDialog(_ExpenseReadService(), expense_id=1)
    qtbot.addWidget(dialog)
    assert dialog.method_combo.currentData() == "BANK"
    assert dialog.status_combo.currentData() == "Pending"


def test_expense_edit_normalizes_legacy_bank_transfer_and_paid_values(qtbot):
    dialog = ExpenseFormDialog(
        _ExpenseReadService(payment_method="Bank Transfer", status="Paid"),
        expense_id=1,
    )
    qtbot.addWidget(dialog)
    assert dialog.method_combo.currentData() == "BANK"
    assert dialog.status_combo.currentData() == "Completed"


def test_expense_other_payment_method_requires_explicit_wallet_resolution(qtbot):
    dialog = ExpenseFormDialog(
        _ExpenseReadService(payment_method="Other", status="Pending"),
        expense_id=1,
    )
    qtbot.addWidget(dialog)
    assert dialog.method_combo.currentData() is None
    assert "requires selection" in dialog.method_combo.currentText()
