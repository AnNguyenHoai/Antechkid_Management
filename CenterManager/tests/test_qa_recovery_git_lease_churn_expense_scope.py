"""Recovery snapshot Git-lease churn and Finance Dashboard expense ledger scope.

All Git/SQLCipher fixtures use isolated synthetic runtimes, never official MAIN.
"""
from datetime import date
from decimal import Decimal
import shutil

import pytest

from tests.test_e1b1_durable_write_recovery import workspace  # noqa: F401
from centermanager.platform.write_recovery import RecoveryRequired
from centermanager.services.finance_dashboard_service import FinanceDashboardService
from centermanager.ui.finance_workspace.finance_dashboard_page import FinanceDashboardPage


def test_git_transport_churn_during_preserve_does_not_falsely_require_recovery(
        workspace, monkeypatch):
    # Git lease/transport metadata changes in real operations while the
    # recovery capture is copying. Neither is a business data mutation.
    repo = workspace.journal.repository
    git_dir = repo / ".git"
    head_ref = git_dir / "refs" / "heads" / "lock-main"
    head_ref.parent.mkdir(parents=True, exist_ok=True)
    head_ref.write_text("a" * 40 + "\n", encoding="ascii")
    original = shutil.copytree
    changed = []
    def copy_and_renew(source, destination, *args, **kwargs):
        result = original(source, destination, *args, **kwargs)
        if source == repo:
            (git_dir / "FETCH_HEAD").write_text("new remote observation", encoding="ascii")
            head_ref.write_text("b" * 40 + "\n", encoding="ascii")
            changed.append(True)
        return result
    monkeypatch.setattr(shutil, "copytree", copy_and_renew)
    capture = workspace.journal.preserve("synthetic-lock-renewal")
    assert changed
    assert workspace.journal.verify_capture(capture)
    assert (capture / "repository" / ".git" / "refs" / "heads" / "lock-main").exists()


@pytest.mark.parametrize("relative", ["manifest.json", "database/center.db"])
def test_business_workspace_mutation_during_preserve_still_fails_closed(
        workspace, monkeypatch, relative):
    repo = workspace.journal.repository
    original = shutil.copytree
    def copy_and_mutate(source, destination, *args, **kwargs):
        result = original(source, destination, *args, **kwargs)
        if source == repo:
            file = repo / relative
            file.write_bytes(file.read_bytes() + b"tamper")
        return result
    monkeypatch.setattr(shutil, "copytree", copy_and_mutate)
    with pytest.raises(RecoveryRequired, match="Workspace changed during preservation"):
        workspace.journal.preserve("synthetic-tamper")


def test_expense_ledger_scope_records_pending_separately():
    class Stub:
        def __init__(self):
            self.calls = []
        def sum_expenses(self, **kwargs):
            self.calls.append(kwargs)
            return Decimal("1900000") if kwargs.get("status") is None else Decimal("1750000")
    expense = Stub()
    service = FinanceDashboardService(income_service=object(), expense_service=expense)
    scope = service._expense_ledger_scope(date(2026, 10, 1), date(2026, 10, 31))
    assert scope == {
        "expense_recorded_period": 1_900_000.0,
        "expense_pending_period": 1_750_000.0,
    }
    assert all(item["finance_period_start"] == date(2026, 10, 1) for item in expense.calls)
    assert all(item["date_to"] == date(2026, 10, 31) for item in expense.calls)
    assert all(item["realized_only"] is False for item in expense.calls)
    info = FinanceDashboardPage._dashboard_scope_text({
        **scope, "expense_period": 150_000, "period_configured": True,
    })
    assert "recorded 1,900,000 VND" in info
    assert "Pending 1,750,000 VND" in info
    assert "paid 150,000 VND" in info


def test_zero_paid_but_recorded_expenses_are_explained_not_counted_as_cash():
    info = FinanceDashboardPage._dashboard_scope_text({
        "period_configured": True, "revenue_period": 35_668_794,
        "expense_period": 0, "expense_recorded_period": 4_500_000,
        "expense_pending_period": 4_500_000,
    })
    assert "recorded 4,500,000 VND" in info
    assert "Pending 4,500,000 VND" in info
    assert "not counted as cash outflow" in info
    assert "Expense status and dates" in info
