from types import SimpleNamespace

from centermanager.core.current_user import CurrentUserContext
from centermanager.ui.finance_workspace.expense_list_page import ExpenseListPage
from centermanager.ui.finance_workspace.income_list_page import IncomeListPage


class _User:
    is_active = True
    is_admin = False
    role = SimpleNamespace(name="finance")

    def __init__(self, permissions):
        self._permissions = set(permissions)

    def has_permission(self, permission_name):
        return permission_name in self._permissions


class _Collaboration:
    def __init__(self):
        self.ensure_write_calls = 0

    def ensure_write(self):
        self.ensure_write_calls += 1
        return True


class _Notification:
    def __init__(self):
        self.messages = []

    def notify(self, message, level):
        self.messages.append((message, level))


def _income_page(qtbot, collaboration=None, notification=None):
    page = IncomeListPage(
        object(),
        object(),
        object(),
        collaboration or _Collaboration(),
        notification,
    )
    qtbot.addWidget(page)
    return page


def _expense_page(qtbot, collaboration=None, notification=None):
    page = ExpenseListPage(
        object(),
        collaboration or _Collaboration(),
        notification,
    )
    qtbot.addWidget(page)
    return page


def test_income_add_requires_write_state_and_create_capability(qtbot):
    with CurrentUserContext(_User({"finance.view"})):
        page = _income_page(qtbot)
        page.set_write_enabled(True)
        assert not page.add_btn.isEnabled()
        assert not page._can_mutate("finance.income.create")

    with CurrentUserContext(_User({"finance.view", "finance.income.create"})):
        page = _income_page(qtbot)
        page.set_write_enabled(False)
        assert not page.add_btn.isEnabled()
        page.set_write_enabled(True)
        assert page.add_btn.isEnabled()
        assert page._can_mutate("finance.income.create")


def test_income_update_and_delete_capabilities_are_independent(qtbot):
    with CurrentUserContext(_User({"finance.view", "finance.income.update"})):
        page = _income_page(qtbot)
        page.set_write_enabled(True)
        assert page._can_mutate("finance.income.update")
        assert not page._can_mutate("finance.income.delete")


def test_expense_add_requires_write_state_and_create_capability(qtbot):
    with CurrentUserContext(_User({"finance.view", "finance.expense.create"})):
        page = _expense_page(qtbot)
        page.set_write_enabled(False)
        assert not page.add_btn.isEnabled()
        page.set_write_enabled(True)
        assert page.add_btn.isEnabled()


def test_expense_update_and_delete_capabilities_are_independent(qtbot):
    with CurrentUserContext(_User({"finance.view", "finance.expense.delete"})):
        page = _expense_page(qtbot)
        page.set_write_enabled(True)
        assert not page._can_mutate("finance.expense.update")
        assert page._can_mutate("finance.expense.delete")


def test_denied_capability_stops_before_write_lock_request(qtbot):
    collaboration = _Collaboration()
    notification = _Notification()
    with CurrentUserContext(_User({"finance.view"})):
        page = _expense_page(qtbot, collaboration, notification)
        page.set_write_enabled(True)
        assert not page._ensure_mutation("finance.expense.create", "add")

    assert collaboration.ensure_write_calls == 0
    assert notification.messages
