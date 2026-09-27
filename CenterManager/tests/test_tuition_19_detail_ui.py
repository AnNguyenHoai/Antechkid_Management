# -*- coding: utf-8 -*-
"""TUITION-19 UI contract for explainable settlement reconciliation."""
from pathlib import Path


def _dialog_source() -> str:
    root = Path(__file__).resolve().parents[1]
    return (
        root / "src/centermanager/ui/finance_workspace/tuition_detail_dialog.py"
    ).read_text(encoding="utf-8")


def test_tuition_detail_renders_canonical_settlement_ledger_without_recalculating_paid():
    source = _dialog_source()

    assert 'tabs.addTab(self._settlement_tab(), "Đối soát học phí")' in source
    assert "self._detail.settlement_ledger" in source
    assert '"Đã đối soát", _money(self._detail.paid)' in source
    assert "entry.amount" in source
    assert "entry.reference" in source
    assert "entry.counterparty_enrollment_id" in source

    settlement_body = source.split("def _settlement_tab", 1)[1].split(
        "def _payment_tab", 1
    )[0]
    assert "TuitionAccrualService" not in settlement_body
    assert "IncomeRepository" not in settlement_body
    assert "sum(" not in settlement_body


def test_tuition_detail_explanation_matches_effective_settlement_scope():
    source = _dialog_source()

    assert "thanh toán, hoàn tiền, điều chỉnh tín dụng và tín dụng chuyển lớp" in source
    assert "các khoản đã đóng chỉ gồm" not in source
    assert "Tuition Income ACTIVE được gắn đúng Enrollment" not in source
    assert 'tabs.addTab(self._payment_tab(), "Lịch sử thanh toán")' in source
