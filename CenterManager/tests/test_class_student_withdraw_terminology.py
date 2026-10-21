# -*- coding: utf-8 -*-
"""Regression contracts for canonical student withdrawal terminology in Class UI."""
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "centermanager"


def test_class_detail_uses_withdraw_not_remove_for_students():
    source = (
        SRC / "ui" / "class_workspace" / "class_detail_page.py"
    ).read_text(encoding="utf-8")

    student_block = source.split("def _update_students", 1)[1].split(
        "def _clear_layout", 1
    )[0]
    handler_block = source.split("def _on_withdraw_student", 1)[1].split(
        "def _on_add_session", 1
    )[0]

    assert 'QPushButton("Withdraw")' in student_block
    assert 'QPushButton("Remove")' not in student_block
    assert "_on_remove_student" not in source
    assert "withdraw_student(" in handler_block
    assert "remove_student(" not in handler_block
    assert "A withdrawal reason is required." in handler_block
    assert "keeps attendance, tuition" in handler_block


def test_class_enrollment_dialog_uses_canonical_withdraw_student_api():
    source = (
        SRC / "ui" / "class_workspace" / "class_enrollment_dialog.py"
    ).read_text(encoding="utf-8")

    assert 'QPushButton("← Withdraw")' in source
    assert "self._class_service.withdraw_student(" in source
    assert "self._class_service.remove_student(" not in source


def test_class_service_keeps_remove_student_as_compatibility_alias_only():
    source = (
        SRC / "services" / "class_service.py"
    ).read_text(encoding="utf-8")

    assert "def withdraw_student(" in source
    assert "def remove_student(" in source

    compatibility = source.split("def remove_student(", 1)[1].split(
        "def get_enrolled_students", 1
    )[0]
    assert "Compatibility alias for legacy callers" in compatibility
    assert "return self.withdraw_student(" in compatibility


def test_teacher_remove_action_remains_assignment_semantics():
    source = (
        SRC / "ui" / "class_workspace" / "class_detail_page.py"
    ).read_text(encoding="utf-8")

    teacher_block = source.split("def _update_teachers", 1)[1].split(
        "def _update_students", 1
    )[0]
    assert 'QPushButton("Remove")' in teacher_block
    assert "_on_remove_teacher" in teacher_block
