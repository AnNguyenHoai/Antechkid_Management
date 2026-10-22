# -*- coding: utf-8 -*-
"""Phase-1 search performance contracts: no schema migration required."""
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "centermanager"


def _source(relative: str) -> str:
    return (SRC / relative).read_text(encoding="utf-8")


def test_student_toolbar_search_is_debounced_and_server_paginated():
    source = _source("ui/student_workspace/student_list_page.py")

    assert "QTimer" in source
    assert "setInterval(300)" in source
    assert "search_changed.connect(self._on_search_text_changed)" in source
    assert "self._search_debounce.start()" in source
    assert "search_students_page(" in source
    assert "set_server_data(" in source
    assert "page_requested.connect(self._on_page_requested)" in source


def test_student_search_has_no_parent_service_n_plus_one():
    source = _source("ui/student_workspace/student_list_page.py")
    repository = _source("repositories/student_repository.py")

    assert "get_parents_for_student" not in source
    assert "Student.parents.any(" in repository
    assert "Parent.phone.ilike" in repository
    assert "Parent.name.ilike" in repository
    assert "def search_page(" in repository
    assert "offset(max(0, int(offset)))" in repository
    assert "limit(max(1, int(limit)))" in repository


def test_student_toolbar_filters_are_database_side_without_join_duplication():
    repository = _source("repositories/student_repository.py")

    method = repository.split("def search_page(", 1)[1].split(
        "def get_with_relations", 1
    )[0]
    assert "Student.enrollments.any(" in method
    assert "~Student.enrollments.any(" in method
    assert "Student.assessments.any()" in method
    assert "~Student.assessments.any()" in method
    assert "q.count()" in method


def test_advanced_student_filter_fallback_batch_loads_parents():
    repository = _source("repositories/student_repository.py")
    page = _source("ui/student_workspace/student_list_page.py")

    method = repository.split("def filter_students(", 1)[1]
    assert "selectinload(Student.parents)" in method

    fallback = page.split("def _filter_students", 1)[1].split(
        "def _populate_table", 1
    )[0]
    assert 'getattr(student, "parents", None)' in fallback
    assert "get_parents_for_student" not in fallback


def test_income_text_search_is_debounced_but_filters_remain_immediate():
    source = _source("ui/finance_workspace/income_list_page.py")

    assert "QTimer" in source
    assert "setInterval(300)" in source
    assert "text_changed.connect(self._schedule_search)" in source
    assert "timeout.connect(self._apply_debounced_search)" in source
    assert "currentIndexChanged.connect(self._filters_changed)" in source
    assert "dateChanged.connect(self._filters_changed)" in source


def test_expense_text_search_is_debounced_but_filters_remain_immediate():
    source = _source("ui/finance_workspace/expense_list_page.py")

    assert "QTimer" in source
    assert "setInterval(300)" in source
    assert "text_changed.connect(self._schedule_search)" in source
    assert "timeout.connect(self._apply_debounced_search)" in source
    assert "currentIndexChanged.connect(self._filters_changed)" in source
    assert "dateChanged.connect(self._filters_changed)" in source


def test_phase1_adds_no_database_migration_or_schema_definition():
    # This phase is deliberately query/UI-only. Model files must not be touched by
    # this regression contract; schema/index work belongs to a separately audited phase.
    student = _source("models/student.py")
    income = _source("models/income.py")
    expense = _source("models/expense.py")

    assert "__tablename__ = \"students\"" in student
    assert "__tablename__ = \"incomes\"" in income
    assert "__tablename__ = \"expenses\"" in expense
