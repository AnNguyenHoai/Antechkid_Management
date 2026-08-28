from pathlib import Path
import ast

ROOT = Path("src/centermanager")
SERVICES = ROOT / "services"


def _tree(path):
    return ast.parse(path.read_text(encoding="utf-8"))


def test_teacher_services_have_explicit_public_contracts():
    expected = {
        "teacher_service.py": {
            "create_teacher", "get_teacher", "list_teachers", "update_teacher",
            "delete_teacher", "restore_teacher", "list_archived_teachers",
        },
        "teacher_assignment_service.py": {
            "assign_teacher_to_class", "unassign_teacher_from_class",
            "get_assigned_classes", "get_teachers_for_class",
            "list_available_classes",
        },
        "teacher_document_service.py": {
            "upload_document", "get_documents_for_teacher",
            "delete_document", "get_teacher_code",
        },
    }
    for filename, methods in expected.items():
        tree = _tree(SERVICES / filename)
        found = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        assert methods <= found


def test_teacher_mutations_use_commit_and_event_bus():
    contracts = {
        "teacher_service.py": (
            "TeacherCreated", "TeacherUpdated", "TeacherArchived", "TeacherRestored"
        ),
        "teacher_assignment_service.py": ("TeacherAssignmentChanged",),
        "teacher_document_service.py": ("TeacherDocumentChanged",),
    }
    for filename, event_names in contracts.items():
        text = (SERVICES / filename).read_text(encoding="utf-8")
        assert "session.commit()" in text
        assert "self._event_bus.publish" in text
        for event_name in event_names:
            assert event_name in text


def test_teacher_write_mutation_order_is_persist_then_publish():
    service_files = [
        SERVICES / "teacher_service.py",
        SERVICES / "teacher_assignment_service.py",
        SERVICES / "teacher_document_service.py",
    ]
    for path in service_files:
        text = path.read_text(encoding="utf-8")
        first_commit = text.find("session.commit()")
        first_publish = text.find("self._event_bus.publish")
        assert first_commit != -1
        assert first_publish != -1
        assert first_commit < first_publish


def test_teacher_document_service_has_storage_failure_boundaries():
    text = (SERVICES / "teacher_document_service.py").read_text(encoding="utf-8")
    assert "except Exception:" in text
    assert "dest_path.unlink()" in text
    assert "session.commit()" in text
    assert "except OSError:" in text
    assert "uuid.uuid4().hex" in text


def test_teacher_workspace_ui_does_not_create_database_engine_directly():
    ui_root = ROOT / "ui" / "teacher_workspace"
    offenders = []
    for path in ui_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "create_production_engine" in text or "sessionmaker(" in text:
            offenders.append(path)
    assert offenders == []


def test_teacher_workspace_write_gating_contract():
    docs = ROOT / "ui" / "teacher_workspace" / "teacher_documents_widget.py"
    detail = ROOT / "ui" / "teacher_workspace" / "teacher_detail_page.py"
    list_page = ROOT / "ui" / "teacher_workspace" / "teacher_list_page.py"

    docs_text = docs.read_text(encoding="utf-8")
    detail_text = detail.read_text(encoding="utf-8")
    list_text = list_page.read_text(encoding="utf-8")

    assert "def set_write_enabled" in docs_text
    assert "upload_btn.setEnabled(self._write_enabled)" in docs_text
    assert "not self._write_enabled" in docs_text
    assert "ensure_write()" in detail_text
    assert "ensure_write()" in list_text


def test_teacher_event_contract_exports_are_complete():
    text = (ROOT / "events" / "__init__.py").read_text(encoding="utf-8")
    for name in (
        "TeacherCreated", "TeacherUpdated", "TeacherArchived", "TeacherRestored",
        "TeacherAssignmentChanged", "TeacherDocumentChanged",
    ):
        assert name in text
