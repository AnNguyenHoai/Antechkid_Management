"""Phase 2 — Architecture Hardening contracts for migrated Student services."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "centermanager" / "services"

STUDENT_SERVICES = {
    "student_export_service.py": "StudentExportService",
    "student_import_service.py": "StudentImportService",
    "student_note_service.py": "StudentNoteService",
}

FORBIDDEN_SESSION_OPERATIONS = {
    "query",
    "execute",
    "scalar",
    "scalars",
    "get",
    "add",
    "add_all",
    "delete",
    "merge",
    "expunge",
    "expire",
    "get_bind",
    "connection",
    "exec_driver_sql",
    "refresh",
}


def _service_ast(filename: str) -> ast.AST:
    return ast.parse((SRC / filename).read_text(encoding="utf-8"), filename=filename)


def test_phase2_student_services_are_provider_backed():
    for filename, class_name in STUDENT_SERVICES.items():
        tree = _service_ast(filename)
        source = (SRC / filename).read_text(encoding="utf-8")
        classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name]
        assert classes, f"{class_name} class missing"
        assert "RepositoryProvider" in source, f"{class_name} must use RepositoryProvider"
        assert "self._repository_provider" in source, f"{class_name} must retain provider dependency"


def test_phase2_student_services_do_not_construct_concrete_repositories():
    forbidden_names = {
        "StudentRepository",
        "NoteRepository",
    }
    for filename, class_name in STUDENT_SERVICES.items():
        tree = _service_ast(filename)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in forbidden_names, f"{class_name} constructs concrete repository {node.func.id}"


def test_phase2_student_services_do_not_call_forbidden_session_methods():
    for filename, class_name in STUDENT_SERVICES.items():
        tree = _service_ast(filename)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in FORBIDDEN_SESSION_OPERATIONS:
                continue
            receiver = node.func.value
            if isinstance(receiver, ast.Name) and receiver.id == "session":
                raise AssertionError(
                    f"{class_name} directly calls forbidden session operation session.{node.func.attr}()"
                )


def test_phase2_student_services_keep_transaction_boundary_explicit():
    source = (SRC / "student_note_service.py").read_text(encoding="utf-8")
    assert "session.commit()" in source, "StudentNoteService must keep transaction completion explicit"
