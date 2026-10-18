# -*- coding: utf-8 -*-
"""Contracts for Outstanding operational visibility of inactive Enrollment history."""
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_outstanding_service_hides_only_paid_inactive_when_operational_default_requested():
    source = (
        ROOT / "src" / "centermanager" / "services" / "outstanding_service.py"
    ).read_text(encoding="utf-8")

    assert "hide_settled_inactive" in source
    assert 'getattr(enrollment, "status", None) in {"WITHDRAWN", "COMPLETED"}' in source
    assert "dto.balance_state == BALANCE_STATE_PAID" in source
    assert "and status_filter is None" in source


def test_outstanding_ui_uses_operational_default_for_page_reload_and_export():
    source = (
        ROOT / "src" / "centermanager" / "ui" / "finance_workspace" / "outstanding_list_page.py"
    ).read_text(encoding="utf-8")

    assert source.count("hide_settled_inactive=True") >= 3


def test_explicit_paid_filter_can_reveal_settled_inactive_history():
    source = (
        ROOT / "src" / "centermanager" / "services" / "outstanding_service.py"
    ).read_text(encoding="utf-8")

    gate = source.split("hide_settled_inactive", 2)[-1]
    assert "status_filter is None" in gate
