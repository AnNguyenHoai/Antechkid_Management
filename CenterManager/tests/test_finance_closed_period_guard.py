from __future__ import annotations

from datetime import date

import pytest

from centermanager.models.finance_period import FinancePeriod
from centermanager.models.financial_settlement import FinancialSettlement
from centermanager.services.expense_service import ExpenseService, ExpenseValidationError
from centermanager.services.finance_ledger_guard import (
    FinanceLedgerGuard,
    FinancePeriodClosedError,
)
from centermanager.services.finance_period_service import FinancePeriodService
from centermanager.services.income_service import IncomeService, IncomeValidationError


class _FinancePeriods:
    def __init__(self, configuration):
        self.configuration = configuration

    def get_unique_effective(self, target_date):
        if self.configuration is None:
            return None
        if target_date < self.configuration.effective_from:
            return None
        if self.configuration.effective_to and target_date > self.configuration.effective_to:
            return None
        return self.configuration

    def get_effective(self, target_date):
        return self.get_unique_effective(target_date)


class _Settlements:
    def __init__(self, row=None):
        self.row = row
        self.seen_start = None

    def get_by_period_start(self, period_start):
        self.seen_start = period_start
        if self.row is not None and self.row.finance_period_start == period_start:
            return self.row
        return None


class _Provider:
    def __init__(self, configuration, settlement=None):
        self.period_repo = _FinancePeriods(configuration)
        self.settlement_repo = _Settlements(settlement)

    def finance_periods(self, session):
        return self.period_repo

    def financial_settlements(self, session):
        return self.settlement_repo


class _Session:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _session_factory():
    return _Session()


def _configuration():
    return FinancePeriod(
        id=7,
        duration_months=1,
        status=FinancePeriod.STATUS_ACTIVE,
        effective_from=date(2026, 9, 15),
        effective_to=date(2026, 10, 14),
    )


def _settlement(status):
    return FinancialSettlement(
        id=9,
        finance_period_start=date(2026, 9, 15),
        finance_period_end=date(2026, 10, 14),
        status=status,
    )


def test_guard_resolves_mid_month_period_and_allows_without_confirmed_settlement():
    provider = _Provider(_configuration())

    resolved = FinanceLedgerGuard.ensure_date_mutable(
        object(), provider, date(2026, 9, 24)
    )

    assert resolved.period_start == date(2026, 9, 15)
    assert resolved.period_end == date(2026, 10, 14)
    assert provider.settlement_repo.seen_start == date(2026, 9, 15)


def test_draft_settlement_does_not_close_ledger():
    provider = _Provider(
        _configuration(), _settlement(FinancialSettlement.STATUS_DRAFT)
    )

    FinanceLedgerGuard.ensure_date_mutable(
        object(), provider, date(2026, 9, 24)
    )


def test_confirmed_settlement_closes_resolved_period():
    provider = _Provider(
        _configuration(), _settlement(FinancialSettlement.STATUS_CONFIRMED)
    )

    with pytest.raises(FinancePeriodClosedError, match="closed by confirmed Settlement"):
        FinanceLedgerGuard.ensure_date_mutable(
            object(), provider, date(2026, 9, 24)
        )


def test_finance_period_status_does_not_define_ledger_closure():
    configuration = _configuration()
    configuration.status = FinancePeriod.STATUS_INACTIVE
    provider = _Provider(configuration, _settlement(FinancialSettlement.STATUS_DRAFT))

    FinanceLedgerGuard.ensure_date_mutable(
        object(), provider, date(2026, 9, 24)
    )


def test_public_finance_period_service_projects_confirmed_closure():
    provider = _Provider(
        _configuration(), _settlement(FinancialSettlement.STATUS_CONFIRMED)
    )
    service = FinancePeriodService(_session_factory, repository_provider=provider)

    assert service.is_period_closed(date(2026, 9, 24)) is True
    with pytest.raises(FinancePeriodClosedError):
        service.ensure_period_is_mutable(date(2026, 9, 24))


def test_income_service_translates_closed_period_to_domain_validation_error():
    provider = _Provider(
        _configuration(), _settlement(FinancialSettlement.STATUS_CONFIRMED)
    )
    service = object.__new__(IncomeService)
    service._repository_provider = provider

    with pytest.raises(IncomeValidationError, match="closed by confirmed Settlement"):
        service._ensure_period_start_mutable(object(), date(2026, 9, 15))


def test_expense_service_translates_closed_period_to_domain_validation_error():
    provider = _Provider(
        _configuration(), _settlement(FinancialSettlement.STATUS_CONFIRMED)
    )
    service = object.__new__(ExpenseService)
    service._repository_provider = provider

    with pytest.raises(ExpenseValidationError, match="closed by confirmed Settlement"):
        service._ensure_date_mutable(object(), date(2026, 9, 24))


def test_source_and_destination_must_both_be_mutable_for_period_move():
    source_provider = _Provider(
        _configuration(), _settlement(FinancialSettlement.STATUS_CONFIRMED)
    )
    destination_config = FinancePeriod(
        id=8,
        duration_months=1,
        status=FinancePeriod.STATUS_ACTIVE,
        effective_from=date(2026, 10, 15),
        effective_to=date(2026, 11, 14),
    )
    destination_provider = _Provider(destination_config)

    with pytest.raises(FinancePeriodClosedError):
        FinanceLedgerGuard.ensure_date_mutable(
            object(), source_provider, date(2026, 9, 24)
        )
    FinanceLedgerGuard.ensure_date_mutable(
        object(), destination_provider, date(2026, 10, 24)
    )
