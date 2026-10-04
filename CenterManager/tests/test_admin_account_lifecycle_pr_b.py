from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "centermanager"


def test_user_delete_is_admin_only_capability():
    source = (SRC / "core" / "capabilities.py").read_text(encoding="utf-8")
    admin_only = source.split("ADMIN_ONLY_CAPABILITIES = frozenset({", 1)[1].split("})", 1)[0]
    assert "Capability.USER_DELETE.value" in admin_only


def test_user_list_exposes_admin_delete_action_with_write_guard():
    source = (SRC / "ui" / "admin_workspace" / "user_list_page.py").read_text(encoding="utf-8")
    assert 'delete_action = QAction("Delete Account Permanently", self)' in source
    assert "PermissionDefinitions.USER_DELETE" in source
    assert "self._write_enabled and can_delete" in source
    assert "def _delete_user(self, user_id: int) -> None:" in source
    assert "self._service.delete_user(user_id)" in source


def test_delete_ui_explains_linked_employee_safety_boundary():
    source = (SRC / "ui" / "admin_workspace" / "user_list_page.py").read_text(encoding="utf-8")
    assert "Employee records and work history are never deleted by this action." in source
    assert "Deactivate the account instead" in source


def test_service_preserves_existing_delete_invariants():
    source = (SRC / "services" / "permission_service.py").read_text(encoding="utf-8")
    assert 'self._ensure_not_current_user(user_id, "delete")' in source
    assert 'self._ensure_not_last_admin(session, user, "delete")' in source
    assert "get_employee_linked_to_user(user_id)" in source
