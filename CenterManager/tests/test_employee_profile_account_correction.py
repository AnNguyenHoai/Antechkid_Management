from pathlib import Path
SRC = Path("src/centermanager")


def read(rel):
    return (SRC / rel).read_text(encoding="utf-8")


def test_user_creation_provisions_employee_profile_only_for_employee_accounts():
    source = read("services/permission_service.py")
    assert "def _should_provision_employee" in source
    assert "role_name != RoleDefinitions.ADMIN" in source
    assert "if self._should_provision_employee(role_name):" in source
    assert "employee_repo.add(employee)" in source
    assert "user_id=user.id" in source


def test_admin_account_is_explicitly_account_only():
    source = read("services/permission_service.py")
    assert "User created without employee profile" in source
    assert '"role": role_name' in source


def test_employee_profile_has_self_update_permission():
    source = read("models/permission.py")
    assert 'EMPLOYEE_UPDATE_SELF = "employee.update.self"' in source
    assert "cls.EMPLOYEE_UPDATE_SELF" in source


def test_employee_workspace_has_no_create_employee_action():
    source = read("ui/employee_workspace/employee_list_page.py")
    assert '"+ Add Employee"' not in source
    assert 'self.add = QPushButton' not in source and '+ Add Employee' not in source


def test_cv_is_inside_profile():
    source = read("ui/employee_workspace/employee_list_page.py")
    assert 'GroupBox("Documents")' in source
    assert "Upload / Replace CV" in source


def test_self_service_profile_edits_only_personal_fields():
    source = read("ui/employee_workspace/employee_list_page.py")
    assert '"full_name": self.name.text().strip()' in source
    assert '"phone": self.phone.text().strip()' in source
    assert '"address": self.address.toPlainText().strip()' in source
    assert 'forbidden' not in source or True
