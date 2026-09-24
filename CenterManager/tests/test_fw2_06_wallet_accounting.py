from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from centermanager.core.wallet import (
    Wallet,
    WalletMappingError,
    canonical_wallet_value,
    resolve_wallet,
    wallet_aliases,
)
from centermanager.repositories.expense_repository import ExpenseRepository
from centermanager.repositories.income_repository import IncomeRepository
from centermanager.services.expense_service import ExpenseService, ExpenseValidationError
from centermanager.services.income_service import IncomeService, IncomeValidationError
from centermanager.services.wallet_service import WalletService


class _IncomeAggregate:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def aggregate_active_amounts_by_payment_method(self, **kwargs):
        self.calls.append(kwargs)
        return self.rows


class _ExpenseAggregate:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def aggregate_realized_amounts_by_payment_method(self, **kwargs):
        self.calls.append(kwargs)
        return self.rows


class _Provider:
    def __init__(self, incomes, expenses):
        self.income_repo = incomes
        self.expense_repo = expenses

    def incomes(self, _session):
        return self.income_repo

    def expenses(self, _session):
        return self.expense_repo


class _Session:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _SessionFactory:
    def __init__(self):
        self.session = _Session()

    def __call__(self):
        return self.session


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("CASH", Wallet.CASH),
        ("Cash", Wallet.CASH),
        ("TÀI KHOẢN CÁ NHÂN", Wallet.CASH),
        ("BANK", Wallet.BANK),
        ("Bank", Wallet.BANK),
        ("Bank Transfer", Wallet.BANK),
        ("TÀI KHOẢN CÔNG TY", Wallet.BANK),
    ],
)
def test_wallet_mapping_resolves_canonical_and_legacy_aliases(value, expected):
    assert resolve_wallet(value) == expected
    assert canonical_wallet_value(value) == expected.value


def test_unknown_wallet_alias_is_never_guessed():
    with pytest.raises(WalletMappingError, match="Unknown wallet alias"):
        resolve_wallet("Other")


def test_wallet_alias_sets_include_canonical_and_legacy_values():
    assert wallet_aliases(Wallet.CASH) == (
        "CASH",
        "Cash",
        "TÀI KHOẢN CÁ NHÂN",
    )
    assert wallet_aliases(Wallet.BANK) == (
        "BANK",
        "Bank",
        "Bank Transfer",
        "TÀI KHOẢN CÔNG TY",
    )


def test_income_and_expense_write_validation_returns_canonical_wallet_values():
    income = object.__new__(IncomeService)
    expense = object.__new__(ExpenseService)

    assert income._validate_payment_method("Cash") == "CASH"
    assert income._validate_payment_method("Bank Transfer") == "BANK"
    assert expense._validate_payment_method("TÀI KHOẢN CÁ NHÂN") == "CASH"
    assert expense._validate_payment_method("TÀI KHOẢN CÔNG TY") == "BANK"

    with pytest.raises(IncomeValidationError, match="Unknown wallet alias"):
        income._validate_payment_method("Other")
    with pytest.raises(ExpenseValidationError, match="Unknown wallet alias"):
        expense._validate_payment_method("Other")


def test_repository_filters_keep_legacy_aliases_readable_after_canonical_writes():
    assert IncomeRepository._payment_method_values("CASH") == (
        "CASH",
        "Cash",
        "TÀI KHOẢN CÁ NHÂN",
    )
    assert ExpenseRepository._payment_method_values("BANK") == (
        "BANK",
        "Bank",
        "Bank Transfer",
        "TÀI KHOẢN CÔNG TY",
    )
    assert IncomeRepository._payment_method_values("Legacy Mystery") == (
        "Legacy Mystery",
    )


def test_wallet_service_aggregates_aliases_into_two_canonical_wallets():
    incomes = _IncomeAggregate(
        [
            ("CASH", Decimal("100.00")),
            ("TÀI KHOẢN CÁ NHÂN", Decimal("20.00")),
            ("Bank Transfer", Decimal("50.00")),
        ]
    )
    expenses = _ExpenseAggregate(
        [
            ("Cash", Decimal("30.00")),
            ("BANK", Decimal("10.00")),
            ("TÀI KHOẢN CÔNG TY", Decimal("5.00")),
        ]
    )
    service = WalletService(
        _SessionFactory(),
        repository_provider=_Provider(incomes, expenses),
    )

    summary = service._calculate_in_session(
        object(),
        period_start=date(2026, 9, 15),
        period_end=date(2026, 10, 14),
        opening_cash=10,
        opening_bank=5,
        realized_only=True,
    )

    assert summary.cash.realized_income == Decimal("120.00")
    assert summary.cash.realized_expense == Decimal("30.00")
    assert summary.cash.expected_closing == Decimal("100.00")
    assert summary.bank.realized_income == Decimal("50.00")
    assert summary.bank.realized_expense == Decimal("15.00")
    assert summary.bank.expected_closing == Decimal("40.00")
    assert summary.realized_income_total == Decimal("170.00")
    assert summary.realized_expense_total == Decimal("45.00")
    assert summary.net_realized_cashflow == Decimal("125.00")

    assert incomes.calls == [
        {
            "finance_period_start": date(2026, 9, 15),
            "date_from": date(2026, 9, 15),
            "date_to": date(2026, 10, 14),
        }
    ]
    assert expenses.calls == [
        {
            "date_from": date(2026, 9, 15),
            "date_to": date(2026, 10, 14),
            "realized_only": True,
        }
    ]


def test_wallet_service_fails_on_unknown_historical_alias_instead_of_dropping_money():
    service = WalletService(
        _SessionFactory(),
        repository_provider=_Provider(
            _IncomeAggregate([("Mystery Wallet", Decimal("100.00"))]),
            _ExpenseAggregate([]),
        ),
    )

    with pytest.raises(ValueError, match="unknown wallet alias"):
        service._calculate_in_session(
            object(),
            period_start=date(2026, 9, 15),
            period_end=date(2026, 10, 14),
            realized_only=True,
        )
