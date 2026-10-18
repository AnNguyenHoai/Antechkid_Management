# -*- coding: utf-8 -*-
"""Contracts for atomic tuition payment + non-cash credit workflow."""
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_income_service_posts_actual_income_and_non_cash_credit_in_one_transaction():
    source = (
        ROOT / "src" / "centermanager" / "services" / "income_service.py"
    ).read_text(encoding="utf-8")
    method = source.split("def create_tuition_payment_with_credit", 1)[1].split(
        '@require_permission("finance.view")', 1
    )[0]

    assert 'income_type="Tuition"' in method
    assert "kind=TuitionAdjustment.KIND_CREDIT" in method
    assert "wallet=None" in method
    assert "income_repo.add(income)" in method
    assert "adjustment_repo.add(adjustment)" in method
    assert method.index("income_repo.add(income)") < method.index("adjustment_repo.add(adjustment)")
    assert method.index("adjustment_repo.add(adjustment)") < method.index("session.commit()")
    assert method.count("session.commit()") == 1


def test_payment_time_credit_does_not_create_marketing_or_fake_wallet():
    service_source = (
        ROOT / "src" / "centermanager" / "services" / "income_service.py"
    ).read_text(encoding="utf-8")
    wallet_source = (
        ROOT / "src" / "centermanager" / "core" / "wallet.py"
    ).read_text(encoding="utf-8")

    assert 'source": "PAYMENT_TIME_DISCOUNT"' in service_source
    assert "wallet=None" in service_source
    assert "MARKETING" not in wallet_source


def test_income_form_exposes_optional_non_cash_tuition_credit_only_on_create():
    source = (
        ROOT / "src" / "centermanager" / "ui" / "finance_workspace" / "income_form_dialog.py"
    ).read_text(encoding="utf-8")

    assert "Có giảm giá / hỗ trợ học phí không phát sinh dòng tiền" in source
    assert "create_tuition_payment_with_credit" in source
    assert "not self._is_edit" in source
    assert "Số tiền thực nhận *" in source


def test_existing_settlement_projection_counts_credit_without_wallet_movement():
    source = (
        ROOT / "src" / "centermanager" / "repositories" / "income_repository.py"
    ).read_text(encoding="utf-8")

    assert "TuitionAdjustment.KIND_CREDIT" in source
    assert "paid" in source
    assert "non_cash_credit" in source
    assert "paid\n            + non_cash_credit" in source
