# -*- coding: utf-8 -*-
"""Authoritative closed-FinancePeriod mutation guard for Wallet V2."""
from __future__ import annotations

from datetime import date

from centermanager.models.finance_period import FinancePeriodDefinition, ResolvedFinancePeriod
from centermanager.repositories.provider import RepositoryProvider


class FinancePeriodClosedError(ValueError):
    """Raised when a realized ledger mutation targets a confirmed period."""


class FinanceLedgerGuard:
    """Derive ledger mutability from Settlement.CONFIRMED.

    FinancePeriod.status remains configuration lifecycle. A resolved operating
    period is closed only when its FinancialSettlement is confirmed.
    """

    @staticmethod
    def resolve_period(
        session,
        repository_provider: RepositoryProvider,
        target_date: date,
    ) -> ResolvedFinancePeriod:
        try:
            configuration = repository_provider.finance_periods(
                session
            ).get_unique_effective(target_date)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        if configuration is None:
            raise ValueError(
                f"No FinancePeriod configuration covers {target_date.isoformat()}."
            )
        return FinancePeriodDefinition.resolved_for_configuration(
            configuration, target_date
        )

    @staticmethod
    def ensure_period_start_mutable(
        session,
        repository_provider: RepositoryProvider,
        period_start: date,
    ) -> None:
        settlement = repository_provider.financial_settlements(
            session
        ).get_by_period_start(period_start)
        if settlement is not None and settlement.is_confirmed:
            raise FinancePeriodClosedError(
                "FinancePeriod ledger is closed by confirmed Settlement "
                f"for period starting {period_start.isoformat()}."
            )

    @classmethod
    def ensure_date_mutable(
        cls,
        session,
        repository_provider: RepositoryProvider,
        target_date: date,
    ) -> ResolvedFinancePeriod:
        resolved = cls.resolve_period(session, repository_provider, target_date)
        cls.ensure_period_start_mutable(
            session, repository_provider, resolved.period_start
        )
        return resolved
