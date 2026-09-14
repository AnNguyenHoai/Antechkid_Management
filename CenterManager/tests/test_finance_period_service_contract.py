from datetime import date

import pytest

from centermanager.core.current_user import set_current_user
from centermanager.models.finance_period import FinancePeriod
from centermanager.services.finance_period_service import FinancePeriodService


class _Admin:
    is_admin = True
    is_active = True
    role = type("Role", (), {"name": "admin"})()

    def has_permission(self, permission_name):
        return permission_name in {"finance.period.view", "finance.period.manage"}


class _Finance:
    is_admin = False
    is_active = True
    role = type("Role", (), {"name": "finance"})()

    def has_permission(self, permission_name):
        return permission_name == "finance.period.view"


def test_period_service_configuration_requires_admin(monkeypatch):
    set_current_user(_Finance())
    service = FinancePeriodService(lambda: None)
    with pytest.raises(Exception):
        service.configure(4, date(2026, 9, 1))

    set_current_user(_Admin())
    assert _Admin.is_admin is True


def test_period_service_bounds_delegate_to_domain():
    start, end = FinancePeriodService.get_period_bounds(
        date(2026, 9, 1), date(2027, 1, 1), 4
    )
    assert (start, end) == (date(2027, 1, 1), date(2027, 4, 30))


def test_period_status_constants_are_stable():
    assert FinancePeriod.STATUS_ACTIVE == "ACTIVE"
    assert FinancePeriod.STATUS_INACTIVE == "INACTIVE"
