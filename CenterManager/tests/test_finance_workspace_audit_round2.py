from datetime import date
from types import SimpleNamespace

from sqlalchemy.orm import sessionmaker

from centermanager.core.current_user import CurrentUserContext
from centermanager.database.engine import create_engine_for_path
from centermanager.events.event_bus import EventBus
from centermanager.events.finance_events import FinanceDataChanged
from centermanager.models.expense import Expense
from centermanager.repositories.expense_repository import ExpenseRepository
from centermanager.services.financial_settlement_service import FinancialSettlementService
from centermanager.services.home_dashboard_service import HomeDashboardService
from centermanager.ui.finance_workspace.expense_form_dialog import ExpenseFormDialog
from centermanager.ui.finance_workspace.finance_workspace_shell import FinanceWorkspaceShell
from centermanager.ui.finance_workspace.financial_settlement_page import FinancialSettlementPage
from centermanager.ui.finance_workspace.income_form_dialog import IncomeFormDialog


class _EmptyStudentService:
    def list_students(self):
        return []


class _EmptyClassService:
    def list_classes(self):
        return []


class _IncomeEditService:
    def __init__(self):
        self.updated = None
        self._event_bus = None

    def get_income(self, _income_id):
        return SimpleNamespace(
            student_id=None,
            class_id=None,
            income_type="Other",
            amount=500_000.0,
            payment_method="Cash",
            payment_date=date(2026, 9, 23),
            payment_period="Tháng 9/2026",
            received_by="Admin",
            note="Old note",
        )

    def update_income(self, **kwargs):
        self.updated = kwargs


class _ExpenseEditService:
    def __init__(self):
        self.updated = None
        self._event_bus = None

    def get_expense(self, _expense_id):
        return SimpleNamespace(
            category="Office Rent",
            description="Rent",
            amount=1_000_000.0,
            payment_method="Cash",
            payment_date=date(2026, 9, 23),
            paid_by="Admin",
            status="Completed",
            note="Old note",
        )

    def update_expense(self, **kwargs):
        self.updated = kwargs

    def set_event_bus(self, event_bus):
        self._event_bus = event_bus


class _FinanceShellIncomeService:
    def __init__(self):
        self._event_bus = None


class _FinanceShellExpenseService:
    def __init__(self):
        self._event_bus = None

    def set_event_bus(self, event_bus):
        self._event_bus = event_bus


class _Collaboration:
    def __init__(self, event_bus):
        self._event_bus = event_bus


class _Dashboard:
    _finance_period_service = None


class _NonAdmin:
    is_admin = False


class _Admin:
    is_admin = True


def test_income_edit_can_clear_optional_fields(qtbot):
    service = _IncomeEditService()
    dialog = IncomeFormDialog(
        service,
        _EmptyStudentService(),
        _EmptyClassService(),
        income_id=1,
    )
    qtbot.addWidget(dialog)

    dialog.period_combo.setCurrentIndex(0)
    dialog.received_by_edit.clear()
    dialog.note_edit.clear()
    dialog._save()

    assert service.updated is not None
    assert service.updated["payment_period"] == ""
    assert service.updated["received_by"] == ""
    assert service.updated["note"] == ""


def test_expense_edit_can_clear_optional_fields(qtbot):
    service = _ExpenseEditService()
    dialog = ExpenseFormDialog(service, expense_id=1)
    qtbot.addWidget(dialog)

    dialog.paid_by_edit.clear()
    dialog.note_edit.clear()
    dialog._save()

    assert service.updated is not None
    assert service.updated["paid_by"] == ""
    assert service.updated["note"] == ""


def test_expense_repository_filters_include_legacy_equivalents(test_db_path):
    engine = create_engine_for_path(test_db_path)
    factory = sessionmaker(bind=engine)
    try:
        with factory() as session:
            session.add_all([
                Expense(
                    category="Office Rent",
                    description="Canonical bank",
                    amount=1,
                    payment_method="Bank",
                    status="Completed",
                    payment_date=date(2026, 9, 1),
                ),
                Expense(
                    category="Office Rent",
                    description="Legacy transfer",
                    amount=2,
                    payment_method="Bank Transfer",
                    status="Paid",
                    payment_date=date(2026, 9, 2),
                ),
                Expense(
                    category="Office Rent",
                    description="Legacy company account",
                    amount=3,
                    payment_method="TÀI KHOẢN CÔNG TY",
                    status="Completed",
                    payment_date=date(2026, 9, 3),
                ),
                Expense(
                    category="Office Rent",
                    description="Legacy personal account",
                    amount=4,
                    payment_method="TÀI KHOẢN CÁ NHÂN",
                    status="Completed",
                    payment_date=date(2026, 9, 4),
                ),
            ])
            session.commit()

            repo = ExpenseRepository(session)
            assert repo.count_active(payment_method="Bank") == 3
            assert repo.count_active(payment_method="Cash") == 1
            assert repo.count_active(status="Completed") == 4
    finally:
        engine.dispose()


def test_settlement_buckets_legacy_expense_payment_methods():
    assert FinancialSettlementService._method_bucket("TÀI KHOẢN CÁ NHÂN") == "cash"
    assert FinancialSettlementService._method_bucket("TÀI KHOẢN CÔNG TY") == "bank"
    assert FinancialSettlementService._method_bucket("Bank Transfer") == "bank"


def test_settlement_ui_is_admin_only_even_in_write_mode(qtbot):
    with CurrentUserContext(_NonAdmin()):
        page = FinancialSettlementPage(settlement_service=object())
        qtbot.addWidget(page)
        page.set_write_enabled(True)
        assert not page.save_btn.isEnabled()
        assert not page.confirm_btn.isEnabled()

    with CurrentUserContext(_Admin()):
        page = FinancialSettlementPage(settlement_service=object())
        qtbot.addWidget(page)
        page.set_write_enabled(True)
        assert page.save_btn.isEnabled()
        assert page.confirm_btn.isEnabled()


def test_finance_shell_reuses_application_event_bus(qtbot):
    shared_bus = EventBus()
    collaboration = _Collaboration(shared_bus)
    income_service = _FinanceShellIncomeService()
    expense_service = _FinanceShellExpenseService()

    shell = FinanceWorkspaceShell(
        income_service=income_service,
        student_service=object(),
        class_service=object(),
        expense_service=expense_service,
        dashboard_service=_Dashboard(),
        outstanding_service=object(),
        collaboration_manager=collaboration,
    )
    qtbot.addWidget(shell)

    assert shell._event_bus is shared_bus
    assert income_service._event_bus is shared_bus
    assert expense_service._event_bus is shared_bus


def test_home_cache_invalidates_on_finance_event():
    event_bus = EventBus()
    service = HomeDashboardService(lambda: None, event_bus=event_bus)
    service._cache = [object()]
    service._cache_invalidated = False

    event_bus.publish(FinanceDataChanged(entity="income", action="created", entity_id=123))

    assert service._cache_invalidated is True
