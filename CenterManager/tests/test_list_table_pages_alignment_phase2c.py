# -*- coding: utf-8 -*-
"""Regression contracts for UI Phase 2C list/table page alignment."""
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
UI = ROOT / "src" / "centermanager" / "ui"


def _source(relative: str) -> str:
    return (UI / relative).read_text(encoding="utf-8")


def test_shared_search_toolbar_has_compact_consistent_surface():
    source = _source("shared/search_toolbar.py")

    assert 'self.setObjectName("SharedSearchToolbar")' in source
    assert 'self.setMaximumWidth(520)' in source
    assert 'self.clear_btn.setAccessibleName("Clear search and filters")' in source


def test_student_list_remains_reference_for_shared_data_heavy_surface():
    source = _source("student_workspace/student_list_page.py")

    assert "toolbar = Toolbar(self)" in source
    assert "self.search_bar = SearchToolbar(" in source
    assert "density=TableDensity.COMPACT" in source
    assert "self.bulk_bar = BulkActionBar(toolbar)" in source


def test_class_list_uses_shared_toolbar_search_bulk_and_compact_table():
    source = _source("class_workspace/class_list_page.py")

    assert "toolbar = Toolbar(self)" in source
    assert "self.search_bar = SearchToolbar(" in source
    assert '"options": ["Active", "Inactive"]' in source
    assert 'self.search_bar.set_filter_value("status", "Active")' in source
    assert "self.bulk_bar = BulkActionBar(toolbar)" in source
    assert "density=TableDensity.COMPACT" in source
    assert 'SecondaryButton("🔄 Refresh")' not in source


def test_teacher_list_uses_one_all_state_and_shared_controls():
    source = _source("teacher_workspace/teacher_list_page.py")

    assert "toolbar = Toolbar(self)" in source
    assert "self.search_bar = SearchToolbar(" in source
    assert '"options": ["Active", "Inactive", "Archived"]' in source
    assert '"options": ["Has Classes", "No Classes"]' in source
    assert '"All Assignments"' not in source
    assert '"All Current"' not in source
    assert "self.bulk_bar = BulkActionBar(toolbar)" in source
    assert "density=TableDensity.COMPACT" in source


def test_employee_list_uses_shared_search_toolbar_and_compact_data_table():
    source = _source("employee_workspace/employee_list_page.py")

    employee_block = source.split("class EmployeeListPage(QWidget):", 1)[1]
    assert "toolbar = Toolbar(self)" in employee_block
    assert "self.search_bar = SearchToolbar(" in employee_block
    assert "self.search = self.search_bar.search_input" in employee_block
    assert 'self.filter = self.search_bar.filter_controls["status"]' in employee_block
    assert "density=TableDensity.COMPACT" in employee_block
    assert 'title = QLabel("Employees")' not in employee_block.split("@staticmethod", 1)[0]


def test_finance_lists_use_shared_search_and_compact_tables_without_filter_rewrite():
    for relative in (
        "finance_workspace/income_list_page.py",
        "finance_workspace/expense_list_page.py",
        "finance_workspace/outstanding_list_page.py",
    ):
        source = _source(relative)
        assert "SearchToolbar(" in source
        assert "density=TableDensity.COMPACT" in source
        assert "SearchBar(" not in source
        assert "COLORS['surface_page']" in source
        assert "COLORS['border_default']" in source


def test_finance_action_labels_no_longer_depend_on_emoji_glyphs():
    income = _source("finance_workspace/income_list_page.py")
    expense = _source("finance_workspace/expense_list_page.py")
    outstanding = _source("finance_workspace/outstanding_list_page.py")

    for source in (income, expense, outstanding):
        assert "🔄" not in source
        assert "⬇" not in source
    assert 'PrimaryButton("Thêm thu nhập")' in income
    assert 'PrimaryButton("Thêm chi phí")' in expense
