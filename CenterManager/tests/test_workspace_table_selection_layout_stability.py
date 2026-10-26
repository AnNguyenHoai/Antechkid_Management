# -*- coding: utf-8 -*-
"""Workspace table selection must never cause vertical layout reflow."""
from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent.parent
UI_ROOT = ROOT / "src" / "centermanager" / "ui"


def _workspace_sources():
    for path in UI_ROOT.glob("*_workspace/*.py"):
        if path.name == "__init__.py":
            continue
        yield path, path.read_text(encoding="utf-8")


def test_no_workspace_inserts_bulk_selection_bar_as_vertical_table_row():
    """Selection feedback belongs in a stable toolbar/side surface, never above a table."""
    forbidden = (
        re.compile(r"\blayout\.addWidget\(self\.bulk_bar\)"),
        re.compile(r"\broot\.addWidget\(self\.bulk_bar\)"),
        re.compile(r"\bmain_layout\.addWidget\(self\.bulk_bar\)"),
        re.compile(r"\bcontent_layout\.addWidget\(self\.bulk_bar\)"),
    )

    violations = []
    for path, source in _workspace_sources():
        if "bulk_bar" not in source:
            continue
        for pattern in forbidden:
            if pattern.search(source):
                violations.append(f"{path.relative_to(ROOT)}: {pattern.pattern}")

    assert not violations, (
        "Bulk/selection controls must not be inserted as a vertical row because "
        "show/hide selection would move the table:\n" + "\n".join(violations)
    )


def test_class_selection_controls_are_inside_fixed_toolbar_row():
    source = (
        UI_ROOT / "class_workspace" / "class_list_page.py"
    ).read_text(encoding="utf-8")

    assert "self.bulk_bar = BulkActionBar(toolbar)" in source
    assert 'toolbar.add_widget(self.bulk_bar, align="end")' in source
    assert "layout.addWidget(self.bulk_bar)" not in source


def test_student_and_teacher_selection_controls_remain_toolbar_bound():
    student = (
        UI_ROOT / "student_workspace" / "student_list_page.py"
    ).read_text(encoding="utf-8")
    teacher = (
        UI_ROOT / "teacher_workspace" / "teacher_list_page.py"
    ).read_text(encoding="utf-8")

    assert "toolbar.add_widget(self.bulk_bar" in student
    assert "layout.addWidget(self.bulk_bar)" not in student

    assert 'toolbar.add_widget(self.bulk_bar, align="end")' in teacher
    assert "layout.addWidget(self.bulk_bar)" not in teacher


def test_shared_data_table_selection_changes_only_selection_state():
    """The shared DataTable itself must not allocate/remove widgets on selection."""
    source = (
        UI_ROOT / "shared" / "data_table.py"
    ).read_text(encoding="utf-8")
    handler = source.split("def _on_selection_changed", 1)[1].split(
        "def _on_context_menu", 1
    )[0]

    assert "selection_changed.emit" in handler
    assert ".addWidget(" not in handler
    assert ".insertWidget(" not in handler
    assert ".setVisible(" not in handler
