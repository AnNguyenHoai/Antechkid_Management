from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

from sqlalchemy.orm import sessionmaker

from centermanager.core.clock import get_clock
from centermanager.core.current_user import get_current_user
from centermanager.models.finance_period import FinancePeriodDefinition
from centermanager.models.financial_settlement import FinancialSettlement
from centermanager.repositories.provider import RepositoryProvider, create_default_repository_provider
from centermanager.services.audit_service import AuditService
from centermanager.services.wallet_service import WalletService


_MONEY_QUANTUM = Decimal("0.01")


class FinancialSettlementService:
    """Reconcile Finance activity against actual cash and bank balances.

    Settlement confirmation is the authoritative ledger-close transition. The
    CONFIRMED snapshot and its audit record are persisted in one database
    transaction; reopening is an explicit audited Admin command.
    """

    def __init__(
        self,
        session_factory: sessionmaker,
        repository_provider: Optional[RepositoryProvider] = None,
        audit_service: Optional[AuditService] = None,
        wallet_service: Optional[WalletService] = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository_provider = repository_provider or create_default_repository_provider()
        self._audit_service = audit_service or AuditService(
            session_factory,
            repository_provider=self._repository_provider,
        )
        self._wallet_service = wallet_service or WalletService(
            session_factory,
            repository_provider=self._repository_provider,
        )

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
            raise PermissionError("Only administrators can save, confirm or reopen financial settlements.")

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
        """Resolve exact canonical bounds using the FW2-01 unique resolver contract."""
        repo = self._repository_provider.finance_periods(session)
        try:
            config = repo.get_unique_effective(target_date)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        if config is None:
            raise ValueError("Finance period is not configured for the selected date.")
        resolved = FinancePeriodDefinition.resolved_for_configuration(config, target_date)
        return resolved.period_start, resolved.period_end

    def _aggregate_activity(
        self,
        session,
        period_start: date,
        period_end: date,
    ) -> dict[str, Decimal]:
        """Consume the canonical Wallet read model inside this transaction."""
        summary = self._wallet_service._calculate_in_session(
            session,
            period_start=period_start,
            period_end=period_end,
            realized_only=True,
        )
        return {
            "income_cash": summary.cash.realized_income,
            "income_bank": summary.bank.realized_income,
            "expense_cash": summary.cash.realized_expense,
            "expense_bank": summary.bank.realized_expense,
        }

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

    def _record_transition_audit(
        self,
        session,
        row: FinancialSettlement,
        action: str,
        details: dict[str, Any],
    ) -> None:
        self._audit_service.record_in_session(
            session,
            action=action,
            module="finance",
            target_type="financial_settlement",
            target_id=row.id,
            target_name=f"Settlement #{row.id}",
            details=details,
            actor=get_current_user(),
            entity_type="FinancialSettlement",
            entity_id=row.id,
            summary=f"{action}: FinancialSettlement#{row.id}",
        )

    def get_settlement(self, target_date: Optional[date] = None) -> Optional[FinancialSettlement]:
        target = target_date or get_clock().today()
        with self._session_factory() as session:
            period_start, _ = self._resolve_period(session, target)
            return self._repository_provider.financial_settlements(session).get_by_period_start(period_start)

    def get_preview(self, target_date: Optional[date] = None) -> dict[str, Any]:
        target = target_date or get_clock().today()
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
        """Persist a DRAFT or atomically confirm a complete live-ledger snapshot."""
        self._require_admin()
        with self._session_factory() as session:
            settlement_repo = self._repository_provider.financial_settlements(session)
            period_start, period_end = self._resolve_period(session, target_date)
            row = settlement_repo.get_by_period_start(period_start)
            if row is not None and row.is_confirmed:
                raise ValueError("Confirmed financial settlement is immutable.")

            previous_status = row.status if row is not None else None
            opening_cash_value = self._money(opening_cash)
            opening_bank_value = self._money(opening_bank)
            actual_cash_value = self._optional_money(actual_closing_cash)
            actual_bank_value = self._optional_money(actual_closing_bank)
            if confirm and (actual_cash_value is None or actual_bank_value is None):
                raise ValueError("Actual closing cash and bank balances are required before confirmation.")

            # Recalculate from the live ledger inside the same transaction that
            # persists the final snapshot and the CONFIRMED state.
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
            row.status = (
                FinancialSettlement.STATUS_CONFIRMED
                if confirm
                else FinancialSettlement.STATUS_DRAFT
            )
            row.confirmed_at = get_clock().now() if confirm else None

            if confirm:
                # Repository-owned flush materializes the settlement identity;
                # closure and audit remain in the caller-owned transaction.
                settlement_repo.flush()
                self._record_transition_audit(
                    session,
                    row,
                    "CONFIRM",
                    {
                        "period_start": period_start.isoformat(),
                        "period_end": period_end.isoformat(),
                        "settlement_id": row.id,
                        "previous_status": previous_status,
                        "status": FinancialSettlement.STATUS_CONFIRMED,
                        "expected_closing_cash": str(row.expected_closing_cash),
                        "expected_closing_bank": str(row.expected_closing_bank),
                        "actual_closing_cash": str(row.actual_closing_cash),
                        "actual_closing_bank": str(row.actual_closing_bank),
                        "difference_cash": str(row.difference_cash),
                        "difference_bank": str(row.difference_bank),
                    },
                )

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
            target_date=target_date or get_clock().today(),
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
            target_date=target_date or get_clock().today(),
            opening_cash=opening_cash,
            opening_bank=opening_bank,
            actual_closing_cash=actual_closing_cash,
            actual_closing_bank=actual_closing_bank,
            comment=comment,
            confirm=True,
        )

    def reopen(
        self,
        *,
        target_date: Optional[date] = None,
        reason: str,
    ) -> FinancialSettlement:
        """Explicitly reopen a CONFIRMED period and audit the transition atomically."""
        self._require_admin()
        reason_value = (reason or "").strip()
        if not reason_value:
            raise ValueError("Reopen reason is required.")

        target = target_date or get_clock().today()
        with self._session_factory() as session:
            settlement_repo = self._repository_provider.financial_settlements(session)
            period_start, period_end = self._resolve_period(session, target)
            row = settlement_repo.get_by_period_start(period_start)
            if row is None:
                raise ValueError("No financial settlement exists for the selected period.")
            if not row.is_confirmed:
                raise ValueError("Only a CONFIRMED financial settlement can be reopened.")

            previous_status = row.status
            previous_confirmed_at = row.confirmed_at
            reopened_at = get_clock().now()
            row.status = FinancialSettlement.STATUS_DRAFT
            row.confirmed_at = None

            self._record_transition_audit(
                session,
                row,
                "REOPEN",
                {
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                    "settlement_id": row.id,
                    "previous_settlement_id": row.id,
                    "previous_status": previous_status,
                    "previous_confirmed_at": (
                        previous_confirmed_at.isoformat()
                        if previous_confirmed_at is not None
                        else None
                    ),
                    "status": FinancialSettlement.STATUS_DRAFT,
                    "reason": reason_value,
                    "reopened_at": reopened_at.isoformat(),
                },
            )
            session.commit()
            settlement_repo.refresh(row)
            return row