"""RV-02 regression inventory for academic, student and teacher recovery hooks.

This is deliberately a source-contract check; runtime SQLCipher transaction
atomicity and WRITE authority are covered by RV02/E1B-2B integration suites.
No service is imported or executed by this audit.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

SERVICES = Path(__file__).resolve().parents[1] / "src" / "centermanager" / "services"

EXPECTED = {
    "assessment_service.py": ("create_assessment", "update_assessment", "delete_assessment"),
    "session_note_service.py": ("create_note", "update_note", "delete_note"),
    "student_note_service.py": ("create_note", "update_note", "delete_note"),
    "student_highlight_service.py": ("create_highlight", "update_highlight", "delete_highlight"),
    "parent_service.py": ("create_parent", "update_parent", "delete_parent"),
    "teacher_service.py": ("create_teacher", "update_teacher", "delete_teacher", "restore_teacher"),
    "teacher_assignment_service.py": ("assign_teacher_to_class", "unassign_teacher_from_class"),
}


def _calls(node: ast.AST) -> list[ast.Call]:
    return sorted(
        (item for item in ast.walk(node) if isinstance(item, ast.Call)),
        key=lambda item: (item.lineno, item.col_offset),
    )


def _callee(call: ast.Call) -> str:
    return ast.unparse(call.func)


@pytest.mark.parametrize("filename, methods", EXPECTED.items())
def test_new_recovery_hooks_surround_business_commit(filename, methods):
    tree = ast.parse((SERVICES / filename).read_text(encoding="utf-8-sig"))
    functions = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    for name in methods:
        assert name in functions, f"{filename}: missing {name}"
        calls = _calls(functions[name])
        records = [call for call in calls if _callee(call) == "record_for_active_write"]
        commits = [call for call in calls if _callee(call).endswith(".commit")]
        mirrors = [call for call in calls if _callee(call) == "mirror_after_successful_commit"]
        assert len(records) == len(commits) == len(mirrors) == 1, (
            filename, name, len(records), len(commits), len(mirrors)
        )
        assert records[0].lineno < commits[0].lineno < mirrors[0].lineno
        event_call = records[0]
        kwargs = {kw.arg: kw.value for kw in event_call.keywords}
        assert "entity_id" in kwargs
        assert "entity_object" in kwargs
        assert "summary_args" in kwargs
        assert isinstance(kwargs["summary_args"], ast.Dict)
        assert all(isinstance(key, ast.Constant) and key.value.endswith("_id")
                   for key in kwargs["summary_args"].keys)
