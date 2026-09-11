from pathlib import Path

ROOT = Path("src/centermanager/ui/admin_workspace")


def test_admin_workspace_does_not_wire_employee_work_data_page():
    """Employee Work Registration belongs to Employee Workspace, not Admin."""
    source = (ROOT / "admin_workspace_shell.py").read_text(encoding="utf-8")
    assert "AdminEmployeeWorkDataPage" not in source
    assert '"employee_work_data"' not in source
    assert "admin_employee_work_data_page" not in source


def test_employee_work_data_page_is_not_an_admin_navigation_contract():
    """The Admin shell owns administrative controls only."""
    source = (ROOT / "admin_workspace_shell.py").read_text(encoding="utf-8")
    assert '"label": "Roles & Permissions"' in source
    assert '"label": "Audit Log"' in source
    assert '"label": "System Operations"' in source
    assert '"label": "Backup & Recovery"' in source
