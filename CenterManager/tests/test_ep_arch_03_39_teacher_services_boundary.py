"""EP-ARCH-03.39 — Teacher service repository boundary contract."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "centermanager" / "services"
INVENTORY = ROOT / "docs" / "architecture" / "EP-ARCH-03_SERVICE_INVENTORY.md"

TEACHER_SERVICES = {
    "teacher_service.py": "TeacherService",
    "teacher_assignment_service.py": "TeacherAssignmentService",
    "teacher_document_service.py": "TeacherDocumentService",
    "teacher_timeline_service.py": "TeacherTimelineService",
}

FORBIDDEN_SESSION_OPERATIONS = (
    "session.query(", "session.execute(", "session.scalar(", "session.scalars(", "session.get(", "session.add(",
    "session.add_all(", "session.delete(", "session.merge(", "session.expunge(", "session.expire(",
    "session.get_bind(", "session.connection(", "session.exec_driver_sql(", "session.refresh(",
)


def test_teacher_services_are_provider_backed():
    for filename, class_name in TEACHER_SERVICES.items():
        source = (SRC / filename).read_text(encoding="utf-8")
        assert "RepositoryProvider" in source, f"{class_name} must use RepositoryProvider"
        assert f"class {class_name}" in source


def test_teacher_services_do_not_construct_concrete_repositories():
    for filename, class_name in TEACHER_SERVICES.items():
        source = (SRC / filename).read_text(encoding="utf-8")
        for forbidden in (
            "TeacherRepository(",
            "TeacherAssignmentRepository(",
            "TeacherDocumentRepository(",
            "TeacherTimelineRepository(",
        ):
            assert forbidden not in source, f"{class_name} constructs {forbidden}"


def test_teacher_services_do_not_use_direct_session_persistence_or_query_operations():
    for filename, class_name in TEACHER_SERVICES.items():
        source = (SRC / filename).read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_SESSION_OPERATIONS:
            assert forbidden not in source, f"{class_name} retains forbidden session operation {forbidden}"


def test_teacher_services_are_documented_as_pass():
    source = INVENTORY.read_text(encoding="utf-8")
    for filename, class_name in TEACHER_SERVICES.items():
        row_start = source.index(f"`{filename}`")
        row = source[row_start : source.index("\n", row_start)]
        assert "| PASS |" in row, row
        assert f"**{class_name}**" in source
    assert "## EP-ARCH-03.39 Teacher services repository boundary" in source
