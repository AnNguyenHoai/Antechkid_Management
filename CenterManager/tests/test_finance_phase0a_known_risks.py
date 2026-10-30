"""Executable reproductions of unresolved Phase 0A finance findings.

These are expected failures until a separate, reviewed correctness fix lands.
"""

from datetime import date
from types import SimpleNamespace

import pytest

from centermanager.services.finance_dashboard_service import FinanceDashboardService
from centermanager.core.wallet import WalletMappingError


@pytest.mark.parametrize("kind", ["income", "expense"])
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="F-25: Dashboard totals currently read only the first 10,000 rows",
)
def test_dashboard_total_includes_transactions_beyond_first_page(kind):
    """A financial total must include the 10,001st realized transaction."""
    rows = [SimpleNamespace(amount=1, payment_method="Cash")] * 10001

    class PagedService:
        def list_incomes(self, **kwargs):
            start = (kwargs["page"] - 1) * kwargs["per_page"]
            return rows[start : start + kwargs["per_page"]], len(rows)

        def list_expenses(self, **kwargs):
            start = (kwargs["page"] - 1) * kwargs["per_page"]
            return rows[start : start + kwargs["per_page"]], len(rows)

    service = FinanceDashboardService(PagedService(), PagedService())
    start, end = date(2026, 10, 1), date(2026, 10, 30)
    if kind == "income":
        result = service.get_revenue_by_payment_method(start, end)
    else:
        result = service.get_expense_by_payment_method(start, end)

    assert result["Cash"] == 10001


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Phase 0A: Dashboard silently buckets unknown historical Wallet aliases as Other",
)
def test_dashboard_rejects_unknown_wallet_alias_instead_of_reporting_a_total():
    class IncomeService:
        def list_incomes(self, **kwargs):
            return [SimpleNamespace(amount=100, payment_method="UNKNOWN_LEGACY")], 1

    service = FinanceDashboardService(IncomeService(), object())
    try:
        service.get_revenue_by_payment_method(date(2026, 10, 1), date(2026, 10, 30))
    except WalletMappingError:
        return
    assert False, "unknown Wallet alias must fail explicitly"
