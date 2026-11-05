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
    "student_document_service.py": ("upload_document", "delete_document"),
    "teacher_document_service.py": ("upload_document", "delete_document"),
    "employee_document_service.py": ("upload",),
    "finance_attachment_service.py": ("add_attachment", "remove_attachment"),
    "permission_service.py": (
        "create_role", "update_role", "delete_role", "create_user",
        "update_user_role", "delete_user", "set_user_active",
        "create_user_with_temp_password", "reset_user_password",
        "update_user", "unlock_user",
    ),
    "financial_settlement_service.py": ("_save", "reopen"),
    "employee_service.py": (
        "create_employee", "create_employee_with_account", "link_existing_user",
        "update_status", "update_employee",
    ),
    "employee_working_time_service.py": (
        "create_booking", "check_in", "check_out", "update_booking",
        "delete_entry", "approve", "lock_month",
    ),
    "employee_schedule_service.py": (
        "add_rule", "update_rule", "delete_rule", "add_exception",
        "delete_exception", "add_week_assignment", "delete_week_assignment",
        "seed_week_from_registration", "seed_week_from_template",
        "publish_week", "freeze_week", "reopen_week_for_override",
    ),
    "employee_work_registration_service.py": (
        "create", "update", "delete", "submit_week", "accept", "reopen",
        "set_submission_deadline", "close_week",
    ),
    "employee_admin_management_service.py": (
        "reopen_period", "delete_registration", "delete_employee",
    ),
    "enrollment_transfer_service.py": ("transfer",),
    "enrollment_reconciliation_service.py": ("mark_legitimate", "reconcile"),

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
        # Compact service methods may put successive statements on one line:
        # `record(...); session.commit(); mirror(...)`. Compare exact AST
        # source coordinates, not only .lineno, and retain strict ordering.
        order = lambda call: (call.lineno, call.col_offset)
        assert order(records[0]) < order(commits[0]) < order(mirrors[0])
        event_call = records[0]
        kwargs = {kw.arg: kw.value for kw in event_call.keywords}
        assert "entity_id" in kwargs
        assert "summary_args" in kwargs
        assert isinstance(kwargs["summary_args"], ast.Dict)
        assert all(
            isinstance(key, ast.Constant)
            and (key.value.endswith("_id") or key.value in {"record_count", "changed_count"})
            for key in kwargs["summary_args"].keys
        )


def test_student_document_delete_keeps_file_until_after_commit():
    """A failed metadata commit may not leave an existing document without bytes."""
    tree = ast.parse((SERVICES / "student_document_service.py").read_text(encoding="utf-8-sig"))
    delete = next(node for node in ast.walk(tree)
                  if isinstance(node, ast.FunctionDef) and node.name == "delete_document")
    calls = _calls(delete)
    commits = [call.lineno for call in calls if _callee(call) == "session.commit"]
    file_unlinks = [call.lineno for call in calls if _callee(call) == "file_path.unlink"]
    assert len(commits) == len(file_unlinks) == 1
    assert commits[0] < file_unlinks[0]


def test_permission_change_role_audit_is_semantically_correct():
    source = (SERVICES / "permission_service.py").read_text(encoding="utf-8-sig")
    role_change = source.split("    def update_user_role(", 1)[1].split("\n    def ", 1)[0]
    assert 'self._audit("USER_ROLE_CHANGED", user)' in role_change
    assert 'self._audit("USER_UNLOCKED", user)' not in role_change
