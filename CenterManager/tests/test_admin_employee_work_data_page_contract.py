from pathlib import Path

ROOT = Path("src/centermanager/ui/admin_workspace")


def test_admin_workspace_wires_employee_work_data_page():
    source = (ROOT / "admin_workspace_shell.py").read_text(encoding="utf-8")
    assert "AdminEmployeeWorkDataPage" in source
    assert '"employee_work_data"' in source
    assert "admin_employee_work_data_page" in source


def test_admin_page_exposes_employee_delete_registration_delete_and_period_reopen():
    source = (ROOT / "admin_employee_work_data_page.py").read_text(encoding="utf-8")
    assert 'QPushButton("Delete Employee")' in source
    assert 'QPushButton("Delete Registration")' in source
    assert 'QPushButton("Re-open Closed Period")' in source
    assert "delete_selected_employee" in source
    assert "delete_selected_registration" in source
    assert "reopen_period" in source


def test_admin_page_requires_reason_before_destructive_or_override_action():
    source = (ROOT / "admin_employee_work_data_page.py").read_text(encoding="utf-8")
    assert "_ask_reason" in source
    assert "Reason for deleting this employee" in source
    assert "Reason for deleting this registration" in source
    assert "Reason for reopening this closed period" in source


def test_admin_reopen_keeps_registration_workflow_state_intact():
    source = (ROOT / "admin_employee_work_data_page.py").read_text(encoding="utf-8")
    assert "Registrations keep their workflow status" in source
    assert "DRAFT registrations become editable again when the period is OPEN" in source
