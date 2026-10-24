# -*- coding: utf-8 -*-
"""Regression contracts for Class Overview and Settlement UX hardening."""
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "centermanager"


def _source(relative: str) -> str:
    return (SRC / relative).read_text(encoding="utf-8")


def test_class_overview_reads_only_active_unreconciled_enrollments():
    repository = _source("repositories/class_repository.py")
    service = _source("services/class_service.py")

    assert "def list_active_with_students" in repository
    assert 'Class.status == "ACTIVE"' in repository
    assert 'enrollment.status == "ACTIVE"' in repository
    assert "enrollment.reconciled_into_enrollment_id.is_(None)" in repository
    assert "selectinload(Class.enrollments).selectinload(Enrollment.student)" in repository
    assert "def get_active_class_overview" in service
    assert '"active_student_count": len(students)' in service


def test_class_workspace_exposes_overview_and_refreshes_it_on_domain_changes():
    shell = _source("ui/class_workspace/class_workspace_shell.py")

    assert "ClassOverviewPage" in shell
    assert '{"id": "overview", "icon": "👥", "label": "Class Overview"}' in shell
    assert "self.overview_page.class_selected.connect(self._on_class_selected)" in shell
    assert 'elif page_id == "overview":' in shell
    assert 'self.header.set_context("Class Workspace", "Class Overview")' in shell
    assert "self.overview_page.refresh()" in shell


def test_class_dashboard_student_kpi_uses_active_unreconciled_enrollments():
    dashboard = _source("ui/class_workspace/class_dashboard_page.py")

    assert "if class_obj.is_active" in dashboard
    assert 'enrollment.status == "ACTIVE"' in dashboard
    assert "enrollment.reconciled_into_enrollment_id is None" in dashboard
    assert "sum(c.student_count for c in classes)" not in dashboard


def test_settlement_uses_numeric_money_editor_and_vnd_formatting():
    page = _source("ui/finance_workspace/financial_settlement_page.py")

    assert "class MoneyLineEdit(QLineEdit)" in page
    assert "QRegularExpressionValidator" in page
    assert 'replace(",", "")' in page
    assert 'return f"{amount:,.0f} ₫"' in page
    assert 'return f"{amount:,.2f} ₫"' in page
    assert "self.opening_cash = self._money_input(optional=False)" in page
    assert "self.actual_cash = self._money_input(optional=True)" in page
    assert "QDoubleSpinBox" not in page


def test_settlement_layout_has_readable_financial_hierarchy():
    page = _source("ui/finance_workspace/financial_settlement_page.py")

    assert 'title = QLabel("Financial Settlement"' in page
    assert 'group = QGroupBox("Reconciliation"' in page
    assert "group.setMinimumWidth(820)" in page
    assert 'self.comment_edit.setMinimumHeight(120)' in page
    assert 'self._row_label("Expected closing", strong=True)' in page
    assert 'self._row_label("Actual closing", strong=True)' in page
    assert 'self._row_label("Difference", strong=True)' in page
    assert 'color = COLORS["state_success"]' in page
    assert 'color = COLORS["state_danger"]' in page


def test_settlement_business_precision_contract_remains_decimal_backed():
    service = _source("services/financial_settlement_service.py")
    model = _source("models/financial_settlement.py")

    assert '_MONEY_QUANTUM = Decimal("0.01")' in service
    assert "Numeric(14, 2)" in model
    assert "def _calculate(" in service
