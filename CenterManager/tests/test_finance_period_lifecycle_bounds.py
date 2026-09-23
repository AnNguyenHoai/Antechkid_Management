from datetime import date
from types import SimpleNamespace

import pytest

from centermanager.models.finance_period import FinancePeriodDefinition
from centermanager.services.finance_dashboard_service import FinanceDashboardService
from centermanager.services.finance_period_service import FinancePeriodService
from centermanager.services.financial_settlement_service import FinancialSettlementService
from centermanager.services.outstanding_service import OutstandingService


class _SessionContext:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, tb):
        return False


class _PeriodRepository:
    def __init__(self, config):
        self._config = config

    def get_effective(self, _target):
        return self._config

    # Outstanding uses the compatibility name.
    def get_active(self, _target):
        return self._config


class _Provider:
    def __init__(self, config):
        self._config = config

    def finance_periods(self, _session):
        return _PeriodRepository(self._config)


class _DashboardPeriodService:
    def __init__(self, config):
        self._config = config

    def get_active_period(self, _target):
        return self._config

    @staticmethod
    def get_period_bounds(anchor, target, duration, effective_to=None):
        return FinancePeriodService.get_period_bounds(
            anchor,
            target,
            duration,
            effective_to,
        )


def _superseded_config():
    return SimpleNamespace(
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 2, 14),
        duration_months=3,
    )


def test_period_for_configuration_clips_bucket_at_effective_to():
    assert FinancePeriodDefinition.period_for_date(
        date(2026, 1, 1), date(2026, 2, 1), 3
    ) == (date(2026, 1, 1), date(2026, 3, 31))

    assert FinancePeriodDefinition.period_for_configuration(
        date(2026, 1, 1),
        date(2026, 2, 1),
        3,
        date(2026, 2, 14),
    ) == (date(2026, 1, 1), date(2026, 2, 14))


def test_period_for_configuration_rejects_target_outside_effective_lifetime():
    with pytest.raises(ValueError, match="later than"):
        FinancePeriodDefinition.period_for_configuration(
            date(2026, 1, 1),
            date(2026, 2, 15),
            3,
            date(2026, 2, 14),
        )


def test_finance_period_service_bounds_preserve_legacy_call_and_support_clipping():
    assert FinancePeriodService.get_period_bounds(
        date(2026, 1, 1), date(2026, 2, 1), 3
    ) == (date(2026, 1, 1), date(2026, 3, 31))
    assert FinancePeriodService.get_period_bounds(
        date(2026, 1, 1),
        date(2026, 2, 1),
        3,
        date(2026, 2, 14),
    ) == (date(2026, 1, 1), date(2026, 2, 14))


def test_settlement_resolver_respects_configuration_effective_to():
    service = FinancialSettlementService(
        lambda: _SessionContext(),
        repository_provider=_Provider(_superseded_config()),
    )
    assert service._resolve_period(object(), date(2026, 2, 1)) == (
        date(2026, 1, 1),
        date(2026, 2, 14),
    )


def test_outstanding_resolver_respects_configuration_effective_to():
    service = OutstandingService(
        lambda: _SessionContext(),
        repository_provider=_Provider(_superseded_config()),
    )
    assert service._resolve_period(object(), date(2026, 2, 1)) == (
        date(2026, 1, 1),
        date(2026, 2, 14),
    )


def test_dashboard_fallback_resolver_respects_configuration_effective_to():
    config = _superseded_config()
    service = FinanceDashboardService(
        SimpleNamespace(_session_factory=None),
        object(),
        finance_period_service=_DashboardPeriodService(config),
    )
    service._get_today_date = lambda: date(2026, 2, 10)

    assert service._resolve_dashboard_period(date(2026, 2, 1)) == (
        date(2026, 1, 1),
        date(2026, 2, 14),
        date(2026, 2, 10),
    )
