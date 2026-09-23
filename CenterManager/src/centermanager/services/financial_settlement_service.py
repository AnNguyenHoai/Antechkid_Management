from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

from sqlalchemy.orm import sessionmaker

from centermanager.core.current_user import get_current_user
from centermanager.models.finance_period import FinancePeriodDefinition
from centermanager.models.financial_settlement import FinancialSettlement
from centermanager.repositories.provider import RepositoryProvider, create_default_repository_provider


_MONEY_QUANTUM = Decimal("0.01")


class FinancialSettlementService:
    """Reconcile Finance activity against actual cash and bank balances."""

    def __init__(
        self,
        session_factory: sessionmaker,
        repository_provider: Optional[RepositoryProvider] = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository_provider = repository_provider or create_default_repository_provider()

    @staticmethod
    def _money(value: Any) -> Decimal:
        if value is None:
            return Decimal("0.00")
        return Decimal(str(value)).quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP)

    @staticmethod
    def _optional_money(value: Any) -> Optional[Decimal]:
        if value is None:
            return None
        return FinancialSettlementService._money(value)

    @staticmethod
    def _require_admin() -> None:
        user = get_current_user()
        if user is None or not getattr(user, "is_admin", False):
            raise PermissionError("Only administrators can save or confirm financial settlements.")

    @staticmethod
    def _require_difference_comment(
        difference_cash: Optional[Decimal],
        difference_bank: Optional[Decimal],
        comment: Optional[str],
    ) -> None:
        """Enforce the reconciliation invariant at the service boundary."""
        has_difference = any(
            difference is not None and difference != Decimal("0.00")
            for difference in (difference_cash, difference_bank)
        )
        if has_difference and not (comment or "").strip():
            raise ValueError(
                "Comment is required when actual balances differ from expected balances."
            )

    def _resolve_period(self, session, target_date: date) -> tuple[date, date]:
        config = self._repository_provider.finance_periods(session).get_effective(target_date)
        if config is None:
            raise ValueError("Finance period is not configured for the selected date.")
        return FinancePeriodDefinition.period_for_date(
            config.effective_from,
            target_date,
            config.duration_months,
        )

    @staticmethod
    def _method_bucket(payment_method: Optional[str]) -> Optional[str]:
        normalized = (payment_method or "").strip().lower().replace("_", " ")
        if normalized in {"cash", "tài khoản cá nhân"}:
            return "cash"
        if normalized in {"bank transfer", "bank", "tài khoản công ty"}:
            return "bank"
        return None

    def _aggregate_activity(self, session, period_start: date, period_end: date) -> dict[str, Decimal]:
        totals = {
            "income_cash": Decimal("0.00"),
            "income_bank": Decimal("0.00"),
            "expense_cash": Decimal("0.00"),
            "expense_bank": Decimal("0.00"),
        }

        incomes = self._repository_provider.incomes(session).list_active(
            finance_period_start=period_start,
            date_from=period_start,
            date_to=period_end,
            offset=0,
            limit=100000,
        )
        for income in incomes:
            bucket = self._method_bucket(income.payment_method)
            if bucket is not None:
                totals[f"income_{bucket}"] += self._money(income.amount)

        expenses = self._repository_provider.expenses(session).list_active(
            date_from=period_start,
            date_to=period_end,
            offset=0,
            limit=100000,
            realized_only=True,
        )
        for expense in expenses:
            bucket = self._method_bucket(expense.payment_method)
            if bucket is not None:
                totals[f"expense_{bucket}"] += self._money(expense.amount)

        return {key: self._money(value) for key, value in totals.items()}

    @staticmethod
    def _calculate(
        opening_cash: Decimal,
        opening_bank: Decimal,
        totals: dict[str, Decimal],
        actual_cash: Optional[Decimal],
        actual_bank: Optional[Decimal],
    ) -> dict[str, Optional[Decimal]]:
        expected_cash = opening_cash + totals["income_cash"] - totals["expense_cash"]
        expected_bank = opening_bank + totals["income_bank"] - totals["expense_bank"]
        return {
            "expected_closing_cash": expected_cash,
            "expected_closing_bank": expected_bank,
            "difference_cash": None if actual_cash is None else actual_cash - expected_cash,
            "difference_bank": None if actual_bank is None else actual_bank - expected_bank,
        }

    @staticmethod
    def _row_payload(row: FinancialSettlement) -> dict[str, Any]:
        return {
            "id": row.id,
            "period_start": row.finance_period_start,
            "period_end": row.finance_period_end,
            "opening_cash": row.opening_cash,
            "opening_bank": row.opening_bank,
            "income_cash": row.income_cash,
            "income_bank": row.income_bank,
            "expense_cash": row.expense_cash,
            "expense_bank": row.expense_bank,
            "expected_closing_cash": row.expected_closing_cash,
            "expected_closing_bank": row.expected_closing_bank,
            "actual_closing_cash": row.actual_closing_cash,
            "actual_closing_bank": row.actual_closing_bank,
            "difference_cash": row.difference_cash,
            "difference_bank": row.difference_bank,
            "comment": row.comment or "",
            "status": row.status,
            "confirmed_at": row.confirmed_at,
        }

    def get_settlement(self, target_date: Optional[date] = None) -> Optional[FinancialSettlement]:
        target = target_date or date.today()
        with self._session_factory() as session:
            period_start, _ = self._resolve_period(session, target)
            return self._repository_provider.financial_settlements(session).get_by_period_start(period_start)

    def get_preview(self, target_date: Optional[date] = None) -> dict[str, Any]:
        target = target_date or date.today()
        with self._session_factory() as session:
            period_start, period_end = self._resolve_period(session, target)
            row = self._repository_provider.financial_settlements(session).get_by_period_start(period_start)

            if row is not None and row.is_confirmed:
                payload = self._row_payload(row)
                payload["period_label"] = f"{period_start:%d/%m/%Y} - {period_end:%d/%m/%Y}"
                return payload

            totals = self._aggregate_activity(session, period_start, period_end)
            opening_cash = self._money(row.opening_cash if row is not None else 0)
            opening_bank = self._money(row.opening_bank if row is not None else 0)
            actual_cash = self._optional_money(row.actual_closing_cash if row is not None else None)
            actual_bank = self._optional_money(row.actual_closing_bank if row is not None else None)
            calculated = self._calculate(opening_cash, opening_bank, totals, actual_cash, actual_bank)
            return {
                "id": row.id if row is not None else None,
                "period_start": period_start,
                "period_end": period_end,
                "period_label": f"{period_start:%d/%m/%Y} - {period_end:%d/%m/%Y}",
                "opening_cash": opening_cash,
                "opening_bank": opening_bank,
                **totals,
                **calculated,
                "actual_closing_cash": actual_cash,
                "actual_closing_bank": actual_bank,
                "comment": row.comment if row is not None and row.comment else "",
                "status": row.status if row is not None else FinancialSettlement.STATUS_DRAFT,
                "confirmed_at": None,
            }

    def _save(
        self,
        *,
        target_date: date,
        opening_cash: Any,
        opening_bank: Any,
        actual_closing_cash: Any = None,
        actual_closing_bank: Any = None,
        comment: Optional[str] = None,
        confirm: bool,
    ) -> FinancialSettlement:
        self._require_admin()
        with self._session_factory() as session:
            settlement_repo = self._repository_provider.financial_settlements(session)
            period_start, period_end = self._resolve_period(session, target_date)
            row = settlement_repo.get_by_period_start(period_start)
            if row is not None and row.is_confirmed:
                raise ValueError("Confirmed financial settlement is immutable.")

            opening_cash_value = self._money(opening_cash)
            opening_bank_value = self._money(opening_bank)
            actual_cash_value = self._optional_money(actual_closing_cash)
            actual_bank_value = self._optional_money(actual_closing_bank)
            if confirm and (actual_cash_value is None or actual_bank_value is None):
                raise ValueError("Actual closing cash and bank balances are required before confirmation.")

            totals = self._aggregate_activity(session, period_start, period_end)
            calculated = self._calculate(
                opening_cash_value,
                opening_bank_value,
                totals,
                actual_cash_value,
                actual_bank_value,
            )
            if confirm:
                self._require_difference_comment(
                    calculated["difference_cash"],
                    calculated["difference_bank"],
                    comment,
                )

            if row is None:
                row = FinancialSettlement(
                    finance_period_start=period_start,
                    finance_period_end=period_end,
                )
                settlement_repo.add(row)

            row.finance_period_end = period_end
            row.opening_cash = opening_cash_value
            row.opening_bank = opening_bank_value
            row.income_cash = totals["income_cash"]
            row.income_bank = totals["income_bank"]
            row.expense_cash = totals["expense_cash"]
            row.expense_bank = totals["expense_bank"]
            row.expected_closing_cash = calculated["expected_closing_cash"]
            row.expected_closing_bank = calculated["expected_closing_bank"]
            row.actual_closing_cash = actual_cash_value
            row.actual_closing_bank = actual_bank_value
            row.difference_cash = calculated["difference_cash"]
            row.difference_bank = calculated["difference_bank"]
            row.comment = (comment or "").strip() or None
            row.status = FinancialSettlement.STATUS_CONFIRMED if confirm else FinancialSettlement.STATUS_DRAFT
            row.confirmed_at = datetime.utcnow() if confirm else None

            session.commit()
            settlement_repo.refresh(row)
            return row

    def save_draft(
        self,
        *,
        target_date: Optional[date] = None,
        opening_cash: Any = 0,
        opening_bank: Any = 0,
        actual_closing_cash: Any = None,
        actual_closing_bank: Any = None,
        comment: Optional[str] = None,
    ) -> FinancialSettlement:
        return self._save(
            target_date=target_date or date.today(),
            opening_cash=opening_cash,
            opening_bank=opening_bank,
            actual_closing_cash=actual_closing_cash,
            actual_closing_bank=actual_closing_bank,
            comment=comment,
            confirm=False,
        )

    def confirm(
        self,
        *,
        target_date: Optional[date] = None,
        opening_cash: Any = 0,
        opening_bank: Any = 0,
        actual_closing_cash: Any,
        actual_closing_bank: Any,
        comment: Optional[str] = None,
    ) -> FinancialSettlement:
        return self._save(
            target_date=target_date or date.today(),
            opening_cash=opening_cash,
            opening_bank=opening_bank,
            actual_closing_cash=actual_closing_cash,
            actual_closing_bank=actual_closing_bank,
            comment=comment,
            confirm=True,
        )
