from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

def test_documents_widget_has_write_gate_and_service_teacher_code():
    text = read("src/centermanager/ui/teacher_workspace/teacher_documents_widget.py")
    assert "def set_write_enabled" in text
    assert "self.upload_btn.setEnabled(self._write_enabled)" in text
    assert "if not self._write_enabled or self._teacher_id is None:" in text
    assert "teacher_code = self._service.get_teacher_code(self._teacher_id)" in text
    assert "create_production_engine" not in text
    assert "sessionmaker" not in text

def test_assignment_dialog_uses_service_not_direct_database():
    text = read("src/centermanager/ui/teacher_workspace/teacher_assignment_dialog.py")
    assert "self._assignment_service.list_available_classes()" in text
    assert "create_production_engine" not in text
    assert "sessionmaker" not in text
    assert "ClassRepository" not in text

def test_teacher_services_expose_ui_data_dependencies():
    doc = read("src/centermanager/services/teacher_document_service.py")
    assignment = read("src/centermanager/services/teacher_assignment_service.py")
    assert "def get_teacher_code" in doc
    assert "def list_available_classes" in assignment

def test_shell_provides_safe_notification_service():
    text = read("src/centermanager/ui/teacher_workspace/teacher_workspace_shell.py")
    assert "class _NullNotificationService" in text
    assert "self._notification_service = _NullNotificationService()" in text
    assert "self._notification_service," in text
