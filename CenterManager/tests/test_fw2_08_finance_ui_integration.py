from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from centermanager.core.capabilities import (
    ADMIN_ONLY_CAPABILITIES,
    Capability,
    PERSISTED_CAPABILITIES,
)
from centermanager.core.current_user import CurrentUserContext
from centermanager.models.finance_period import FinancePeriod, ResolvedFinancePeriod
from centermanager.services.authorization_service import AuthorizationService
from centermanager.services.finance_period_service import FinancePeriodService
from centermanager.ui.finance_workspace.finance_workspace_shell import FinanceWorkspaceShell


class _Session:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _SessionFactory:
    def __call__(self):
        return _Session()


class _Periods:
    def __init__(self, rows):
        self.rows = rows

    def list_all(self):
        return list(self.rows)


class _Provider:
    def __init__(self, periods):
        self.periods = periods

    def finance_periods(self, _session):
        return self.periods


def _principal(role: str, *permissions: str):
    return SimpleNamespace(
        role=SimpleNamespace(name=role),
        permissions=list(permissions),
        is_active=True,
    )


def test_settlement_capability_vocabulary_and_admin_only_boundary():
    assert Capability.FINANCE_SETTLEMENT_VIEW.value in PERSISTED_CAPABILITIES
    assert Capability.FINANCE_SETTLEMENT_CREATE.value in PERSISTED_CAPABILITIES
    assert Capability.FINANCE_SETTLEMENT_UPDATE.value in PERSISTED_CAPABILITIES
    assert Capability.FINANCE_SETTLEMENT_CONFIRM.value in ADMIN_ONLY_CAPABILITIES
    assert Capability.FINANCE_SETTLEMENT_REOPEN.value in ADMIN_ONLY_CAPABILITIES
    assert Capability.FINANCE_SETTLEMENT_CONFIRM.value not in PERSISTED_CAPABILITIES
    assert Capability.FINANCE_SETTLEMENT_REOPEN.value not in PERSISTED_CAPABILITIES


def test_finance_and_manager_can_edit_draft_but_cannot_close_or_reopen():
    draft_permissions = (
        Capability.FINANCE_SETTLEMENT_VIEW.value,
        Capability.FINANCE_SETTLEMENT_CREATE.value,
        Capability.FINANCE_SETTLEMENT_UPDATE.value,
    )
    for role in ("finance", "manager"):
        user = _principal(role, *draft_permissions)
        assert AuthorizationService.allows(user, Capability.FINANCE_SETTLEMENT_VIEW)
        assert AuthorizationService.allows(user, Capability.FINANCE_SETTLEMENT_CREATE)
        assert AuthorizationService.allows(user, Capability.FINANCE_SETTLEMENT_UPDATE)
        assert not AuthorizationService.allows(user, Capability.FINANCE_SETTLEMENT_CONFIRM)
        assert not AuthorizationService.allows(user, Capability.FINANCE_SETTLEMENT_REOPEN)


def test_admin_only_settlement_close_and_reopen_are_role_derived():
    admin = _principal(
        "admin",
        Capability.FINANCE_SETTLEMENT_VIEW.value,
        Capability.FINANCE_SETTLEMENT_CREATE.value,
        Capability.FINANCE_SETTLEMENT_UPDATE.value,
    )
    assert AuthorizationService.allows(admin, Capability.FINANCE_SETTLEMENT_VIEW)
    assert AuthorizationService.allows(admin, Capability.FINANCE_SETTLEMENT_CONFIRM)
    assert AuthorizationService.allows(admin, Capability.FINANCE_SETTLEMENT_REOPEN)


def test_resolved_period_enumeration_preserves_mid_month_and_multi_month_identity():
    configuration = FinancePeriod(
        id=1,
        duration_months=2,
        status=FinancePeriod.STATUS_ACTIVE,
        effective_from=date(2026, 6, 15),
        effective_to=None,
    )
    service = FinancePeriodService(
        _SessionFactory(),
        repository_provider=_Provider(_Periods([configuration])),
    )
    user = _principal("finance", Capability.FINANCE_VIEW.value)

    with CurrentUserContext(user):
        periods = service.list_resolved_periods(date(2026, 9, 24))

    assert [(item.period_start, item.period_end) for item in periods] == [
        (date(2026, 8, 15), date(2026, 10, 14)),
        (date(2026, 6, 15), date(2026, 8, 14)),
    ]


def test_period_selector_label_exposes_exact_bounds_and_current_marker():
    period = ResolvedFinancePeriod(
        configuration_id=1,
        period_start=date(2026, 9, 15),
        period_end=date(2026, 10, 14),
    )
    assert FinanceWorkspaceShell._period_display_label(
        period, date(2026, 9, 24)
    ) == "Current · 15/09/2026 – 14/10/2026"
    assert FinanceWorkspaceShell._target_date_for_period(
        period, date(2026, 9, 24)
    ) == date(2026, 9, 24)
    assert FinanceWorkspaceShell._target_date_for_period(
        period, date(2026, 11, 1)
    ) == date(2026, 9, 15)


def test_finance_workspace_no_longer_uses_month_year_as_accounting_selector():
    source = Path(
        "src/centermanager/ui/finance_workspace/finance_workspace_shell.py"
    ).read_text(encoding="utf-8")
    assert "month_combo" not in source
    assert "year_combo" not in source
    assert "list_resolved_periods" in source
    assert "period_start" in source
    assert "period_end" in source


def test_realized_write_forms_offer_only_cash_and_bank_wallet_values():
    income_source = Path(
        "src/centermanager/ui/finance_workspace/income_form_dialog.py"
    ).read_text(encoding="utf-8")
    expense_source = Path(
        "src/centermanager/ui/finance_workspace/expense_form_dialog.py"
    ).read_text(encoding="utf-8")

    for source in (income_source, expense_source):
        assert 'addItem("Cash", "CASH")' in source
        assert 'addItem("Bank", "BANK")' in source
        assert 'addItem("Other", "Other")' not in source
        assert "resolve_wallet" in source


def test_ui_action_projection_uses_authorization_service_not_local_role_rules():
    source = Path(
        "src/centermanager/ui/finance_workspace/action_state.py"
    ).read_text(encoding="utf-8")
    assert "AuthorizationService.allows" in source
    assert "is_admin" not in source
    assert "role.name" not in source
