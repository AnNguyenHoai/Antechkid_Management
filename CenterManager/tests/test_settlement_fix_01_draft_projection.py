"""SETTLEMENT-FIX-01: first Draft PK/Recovery and interactive balance preview."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from centermanager.models.financial_settlement import FinancialSettlement
from centermanager.services.financial_settlement_service import FinancialSettlementService
from centermanager.services.recovery_change_outbox import _safe_summary_args
from centermanager.ui.finance_workspace.financial_settlement_page import (
    FinancialSettlementPage,
)


class Session:
    def __init__(self):
        self.commits = 0
    def __enter__(self):
        return self
    def __exit__(self, *_args):
        return False
    def commit(self):
        self.commits += 1


class DelayedIdentityRepository:
    def __init__(self):
        self.row = None
        self.flushed = 0
        self.refreshed = 0
    def get_by_period_start(self, _date):
        return self.row
    def add(self, row):
        self.row = row
        # Real SQLite assigns PK at flush, not at add().
        assert row.id is None
    def flush(self):
        self.flushed += 1
        if self.row.id is None:
            self.row.id = 42
    def refresh(self, row):
        self.refreshed += 1


def make_service(session, repository):
    class Provider:
        def financial_settlements(self, _session):
            return repository
    class Audit:
        def record_in_session(self, *args, **kwargs):
            pass
    service = FinancialSettlementService(
        lambda: session, repository_provider=Provider(), audit_service=Audit(),
        wallet_service=object(),
    )
    service._require_capability = lambda capability: None
    service._require_admin = lambda: None
    service._resolve_period = lambda session, target: (
        date(2026, 10, 1), date(2026, 10, 31),
    )
    service._aggregate_activity = lambda session, start, end: {
        "income_cash": Decimal("300"),
        "income_bank": Decimal("500"),
        "expense_cash": Decimal("200"),
        "expense_bank": Decimal("100"),
    }
    return service


def test_first_draft_gets_scalar_pk_before_outbox_and_single_commit(monkeypatch):
    from centermanager.services import financial_settlement_service as module
    session, repo = Session(), DelayedIdentityRepository()
    service = make_service(session, repo)
    captured = []

    def outbox(_session, **kwargs):
        # Exercise actual scalar validator rather than a permissive mock.
        _safe_summary_args(kwargs["summary_args"])
        assert kwargs["entity_id"] == 42
        assert kwargs["summary_args"]["settlement_id"] == 42
        assert repo.flushed == 1
        assert session.commits == 0
        captured.append(kwargs)
    monkeypatch.setattr(module, "record_for_active_write", outbox)
    monkeypatch.setattr(module, "mirror_after_successful_commit", lambda _session: None)

    row = service.save_draft(
        target_date=date(2026, 10, 10),
        opening_cash=18000000, opening_bank=25000000,
        actual_closing_cash=18100000, actual_closing_bank=25400000,
    )
    assert row.id == 42
    assert row.status == FinancialSettlement.STATUS_DRAFT
    assert row.opening_cash == Decimal("18000000.00")
    assert row.expected_closing_cash == Decimal("18000100.00")
    assert row.expected_closing_bank == Decimal("25400000.00")
    assert repo.flushed == 1
    assert repo.refreshed == 1
    assert session.commits == 1
    assert len(captured) == 1


def test_outbox_rejection_happens_before_commit_and_draft_stays_unaccepted(monkeypatch):
    from centermanager.services import financial_settlement_service as module
    session, repo = Session(), DelayedIdentityRepository()
    service = make_service(session, repo)
    def outbox(_session, **kwargs):
        raise ValueError("recovery provenance denied")
    monkeypatch.setattr(module, "record_for_active_write", outbox)
    with pytest.raises(ValueError, match="recovery provenance denied"):
        service.save_draft(target_date=date(2026, 10, 10), opening_cash=900)
    assert repo.flushed == 1
    assert session.commits == 0


class Field:
    def __init__(self, value):
        self.value = value
        self.text_value = None
    def money_value(self):
        return self.value
    def setText(self, value):
        self.text_value = value


def fake_page():
    page = SimpleNamespace(
        _projection_totals={
            "income_cash": Decimal("15000000"),
            "income_bank": Decimal("300"),
            "expense_cash": Decimal("15200000"),
            "expense_bank": Decimal("50"),
        },
        opening_cash=Field(Decimal("18103000")),
        opening_bank=Field(Decimal("1200")),
        actual_cash=Field(Decimal("17900000")),
        actual_bank=Field(Decimal("1400")),
        expected_cash=Field(None),
        expected_bank=Field(None),
        difference_cash=Field(None),
        difference_bank=Field(None),
        _format_money=FinancialSettlementPage._format_money,
        _set_difference=lambda label, value: setattr(label, "value", value),
    )
    return page


def test_expected_closing_and_difference_update_immediately_without_save():
    page = fake_page()
    FinancialSettlementPage._update_live_projection(page)
    assert page.expected_cash.text_value == "17,903,000 ₫"
    assert page.expected_bank.text_value == "1,450 ₫"
    assert page.difference_cash.value == Decimal("-3000")
    assert page.difference_bank.value == Decimal("-50")

    page.opening_cash.value = Decimal("18303000")
    FinancialSettlementPage._update_live_projection(page, "changed")
    assert page.expected_cash.text_value == "18,103,000 ₫"
    assert page.difference_cash.value == Decimal("-203000")


def test_blank_actual_balance_is_not_fabricated_as_zero():
    page = fake_page()
    page.actual_cash.value = None
    FinancialSettlementPage._update_live_projection(page)
    assert page.difference_cash.value is None
    assert page.expected_cash.text_value == "17,903,000 ₫"


def test_ui_signal_wiring_recalculates_without_automatic_save():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "src" / "centermanager"
    source = (root / "ui" / "finance_workspace" / "financial_settlement_page.py").read_text(encoding="utf-8")
    assert source.count("editor.textChanged.connect(self._update_live_projection)") == 2
    projection = source.split("def _update_live_projection(", 1)[1].split("def _notify(", 1)[0]
    assert "_projection_totals" in projection
    assert "FinancialSettlementService._calculate(" in projection
    assert "save_draft(" not in projection
    assert "session.commit(" not in projection
