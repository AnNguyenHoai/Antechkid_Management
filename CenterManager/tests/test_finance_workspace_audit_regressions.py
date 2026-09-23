from datetime import date
from types import SimpleNamespace

from centermanager.core.current_user import CurrentUserContext
from centermanager.models.finance_period import FinancePeriodDefinition
from centermanager.services.finance_period_service import FinancePeriodService
from centermanager.ui.finance_workspace.expense_form_dialog import ExpenseFormDialog
from centermanager.ui.finance_workspace.expense_list_page import ExpenseListPage
from centermanager.ui.finance_workspace.finance_workspace_shell import FinanceWorkspaceShell
from centermanager.ui.finance_workspace.income_form_dialog import IncomeFormDialog
from centermanager.ui.finance_workspace.income_list_page import IncomeListPage


class _EmptyStudentService:
    def list_students(self):
        return []


class _EmptyClassService:
    def list_classes(self):
        return []


class _ExpenseReadService:
    def get_expense(self, _expense_id):
        return SimpleNamespace(
            category="Office Rent",
            description="September rent",
            amount=5_000_000.0,
            payment_method="Bank",
            payment_date=date(2026, 9, 20),
            paid_by="Admin",
            status="Pending",
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


def test_current_month_selector_resolves_from_today_not_day_one():
    today = date(2026, 9, 23)
    target = FinanceWorkspaceShell._target_date_for_selection(2026, 9, today)
    assert target == today

    # A mid-month one-month FinancePeriod would previously resolve September 1
    # to the prior bucket (15 Aug - 14 Sep), while a newly-created transaction
    # defaulted to September 23 and landed in the next bucket.
    period_start, period_end = FinancePeriodDefinition.period_for_date(
        date(2026, 8, 15), target, 1
    )
    assert period_start == date(2026, 9, 15)
    assert period_end == date(2026, 10, 14)


def test_historical_month_selector_keeps_stable_day_one_anchor():
    today = date(2026, 9, 23)
    assert FinanceWorkspaceShell._target_date_for_selection(2026, 8, today) == date(
        2026, 8, 1
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
    assert dialog.method_combo.currentData() == "Bank"
    assert dialog.status_combo.currentData() == "Pending"


def test_income_and_expense_default_transaction_date_stays_inside_selected_period():
    period_start = date(2026, 8, 15)
    period_end = date(2026, 9, 14)

    income_page = IncomeListPage.__new__(IncomeListPage)
    income_page._period_start = period_start
    income_page._period_end = period_end
    income_page._target_date = date(2026, 9, 1)

    expense_page = ExpenseListPage.__new__(ExpenseListPage)
    expense_page._period_start = period_start
    expense_page._period_end = period_end
    expense_page._target_date = date(2026, 9, 1)

    # The helper must never default a newly-created row outside the visible
    # period. Since the selected target is inside it, both use that target.
    assert income_page._default_transaction_date() == date(2026, 9, 1)
    assert expense_page._default_transaction_date() == date(2026, 9, 1)
