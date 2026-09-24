from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable, Optional, Tuple

from sqlalchemy.orm import sessionmaker

from centermanager.core.permission_guard import require_permission
from centermanager.core.wallet import Wallet, resolve_wallet
from centermanager.dto.wallet_dto import WalletBalanceDTO, WalletPeriodSummaryDTO
from centermanager.repositories.provider import (
    RepositoryProvider,
    create_default_repository_provider,
)


_MONEY_QUANTUM = Decimal("0.01")


class WalletService:
    """Canonical Wallet V2 read model over realized Income and Expense.

    This service owns the Cash/Bank aggregation semantics. Unknown historical
    aliases fail explicitly so live accounting never guesses or silently drops
    money. Settlement may call ``_calculate_in_session`` inside its own atomic
    confirmation transaction.
    """

    def __init__(
        self,
        session_factory: sessionmaker,
        repository_provider: Optional[RepositoryProvider] = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository_provider = (
            repository_provider or create_default_repository_provider()
        )

    @staticmethod
    def _money(value: Any) -> Decimal:
        if value is None:
            return Decimal("0.00")
        return Decimal(str(value)).quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP)

    def _sum_rows(
        self,
        rows: Iterable[Tuple[Optional[str], Any]],
        *,
        source: str,
    ) -> dict[Wallet, Decimal]:
        totals = {
            Wallet.CASH: Decimal("0.00"),
            Wallet.BANK: Decimal("0.00"),
        }
        for payment_method, amount in rows:
            try:
                wallet = resolve_wallet(payment_method)
            except ValueError as exc:
                raise ValueError(
                    f"{source} contains an unknown wallet alias {payment_method!r}; "
                    "reconciliation cannot continue safely."
                ) from exc
            totals[wallet] += self._money(amount)
        return {wallet: self._money(amount) for wallet, amount in totals.items()}

    def _calculate_in_session(
        self,
        session,
        *,
        period_start: date,
        period_end: date,
        opening_cash: Any = 0,
        opening_bank: Any = 0,
        realized_only: bool = True,
    ) -> WalletPeriodSummaryDTO:
        """Calculate complete Wallet activity in the caller transaction.

        Live accounting callers must pass ``realized_only=True``. The argument
        remains explicit so Settlement keeps ownership of its realized-ledger
        policy while WalletService owns canonical mapping and aggregation.
        """

        income_rows = self._repository_provider.incomes(
            session
        ).aggregate_active_amounts_by_payment_method(
            finance_period_start=period_start,
            date_from=period_start,
            date_to=period_end,
        )
        expense_rows = self._repository_provider.expenses(
            session
        ).aggregate_realized_amounts_by_payment_method(
            date_from=period_start,
            date_to=period_end,
            realized_only=realized_only,
        )

        income = self._sum_rows(income_rows, source="Income ledger")
        expense = self._sum_rows(expense_rows, source="Expense ledger")
        opening = {
            Wallet.CASH: self._money(opening_cash),
            Wallet.BANK: self._money(opening_bank),
        }

        def balance(wallet: Wallet) -> WalletBalanceDTO:
            expected = opening[wallet] + income[wallet] - expense[wallet]
            return WalletBalanceDTO(
                wallet=wallet,
                opening_balance=opening[wallet],
                realized_income=income[wallet],
                realized_expense=expense[wallet],
                expected_closing=self._money(expected),
            )

        return WalletPeriodSummaryDTO(
            period_start=period_start,
            period_end=period_end,
            cash=balance(Wallet.CASH),
            bank=balance(Wallet.BANK),
        )

    @require_permission("finance.view")
    def get_period_summary(
        self,
        *,
        period_start: date,
        period_end: date,
        opening_cash: Any = 0,
        opening_bank: Any = 0,
    ) -> WalletPeriodSummaryDTO:
        with self._session_factory() as session:
            return self._calculate_in_session(
                session,
                period_start=period_start,
                period_end=period_end,
                opening_cash=opening_cash,
                opening_bank=opening_bank,
                realized_only=True,
            )
