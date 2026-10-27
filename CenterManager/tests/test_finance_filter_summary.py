# -*- coding: utf-8 -*-
"""Regression contracts for filtered Finance list summaries."""
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "centermanager"


def _source(relative: str) -> str:
    return (SRC / relative).read_text(encoding="utf-8")


def test_income_repository_sums_with_same_filter_pipeline_as_list_and_count():
    source = _source("repositories/income_repository.py")

    assert "def sum_records(" in source
    assert "func.coalesce(func.sum(Income.amount), 0)" in source
    assert "query = self._apply_filters(" in source
    assert "return self._decimal(query.scalar())" in source


def test_expense_repository_sums_with_same_filtered_query_as_list_and_count():
    source = _source("repositories/expense_repository.py")

    assert "def sum_filtered_amount(" in source
    assert "query = self._filtered_query(" in source
    assert ".with_entities(func.coalesce(func.sum(Expense.amount), 0))" in source
    assert "return Decimal(str(query.scalar() or 0))" in source


def test_income_service_exposes_filtered_sum_without_pagination_arguments():
    source = _source("services/income_service.py")

    start = source.index("def sum_incomes(")
    end = source.index('@require_permission("finance.income.update")', start)
    body = source[start:end]
    assert "repo.sum_records(" in body
    assert "page" not in body
    assert "per_page" not in body
    assert "sort_by" not in body


def test_expense_service_exposes_filtered_sum_without_pagination_arguments():
    source = _source("services/expense_service.py")

    start = source.index("def sum_expenses(")
    end = source.index('@require_permission("finance.view")\n    def export_expenses_csv', start)
    body = source[start:end]
    assert "repo.sum_filtered_amount(" in body
    assert "page" not in body
    assert "per_page" not in body
    assert "sort_by" not in body


def test_income_list_summary_uses_entire_filtered_result_set():
    source = _source("ui/finance_workspace/income_list_page.py")

    assert "self._filtered_amount = 0" in source
    assert "self.summary_bar = FilterSummaryBar(" in source
    assert 'amount_label="Tổng giá trị thu theo bộ lọc:"' in source
    assert "self._income_service.sum_incomes(" in source
    assert "self.summary_bar.set_summary(self._total_rows, self._filtered_amount)" in source
    assert "sum(income.amount for income in self._incomes)" not in source


def test_expense_list_summary_uses_entire_filtered_result_set():
    source = _source("ui/finance_workspace/expense_list_page.py")

    assert "self._filtered_amount = 0" in source
    assert "self.summary_bar = FilterSummaryBar(" in source
    assert 'amount_label="Tổng giá trị chi theo bộ lọc:"' in source
    assert "self._service.sum_expenses(" in source
    assert "self.summary_bar.set_summary(self._total_rows, self._filtered_amount)" in source
    assert "sum(exp.amount for exp in self._expenses)" not in source


def test_filter_summary_bar_formats_count_and_vnd_amount():
    source = _source("ui/shared/filter_summary_bar.py")

    assert 'self.count_label.setText(f"{int(count):,} giao dịch phù hợp")' in source
    assert 'self.amount_value.setText(f"{value:,.0f} {self._currency}")' in source
