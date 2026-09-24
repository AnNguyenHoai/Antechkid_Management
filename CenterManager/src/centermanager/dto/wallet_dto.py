from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from centermanager.core.wallet import Wallet


@dataclass(frozen=True)
class WalletBalanceDTO:
    wallet: Wallet
    opening_balance: Decimal
    realized_income: Decimal
    realized_expense: Decimal
    expected_closing: Decimal

    @property
    def movement(self) -> Decimal:
        return self.realized_income - self.realized_expense


@dataclass(frozen=True)
class WalletPeriodSummaryDTO:
    period_start: date
    period_end: date
    cash: WalletBalanceDTO
    bank: WalletBalanceDTO

    def for_wallet(self, wallet: Wallet) -> WalletBalanceDTO:
        if wallet == Wallet.CASH:
            return self.cash
        if wallet == Wallet.BANK:
            return self.bank
        raise ValueError(f"Unsupported wallet: {wallet!r}")

    @property
    def realized_income_total(self) -> Decimal:
        return self.cash.realized_income + self.bank.realized_income

    @property
    def realized_expense_total(self) -> Decimal:
        return self.cash.realized_expense + self.bank.realized_expense

    @property
    def net_realized_cashflow(self) -> Decimal:
        return self.realized_income_total - self.realized_expense_total
