from pathlib import Path


SERVICES_DIR = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "centermanager"
    / "services"
)


FORBIDDEN_REPOSITORY_IMPORT_MARKER = "from centermanager.repositories."
FORBIDDEN_REPOSITORY_CONSTRUCTION_MARKER = "Repository("


MIGRATED_SERVICES = {
    "assessment_service.py",
    "attendance_service.py",
    "class_service.py",
    "class_timeline_service.py",
    "employee_admin_management_service.py",
    "employee_document_service.py",
    "employee_schedule_service.py",
    "employee_service.py",
    "employee_work_registration_service.py",
    "employee_working_time_service.py",
    "enrollment_service.py",
    "expense_timeline_service.py",
    "income_service.py",
    "permission_service.py",
    "report_service.py",
    "student_note_service.py",
    "student_service.py",
    "teacher_assignment_service.py",
    "teacher_document_service.py",
    "teacher_service.py",
}


def test_migrated_services_have_no_concrete_repository_imports():
    for filename in sorted(MIGRATED_SERVICES):
        source = (SERVICES_DIR / filename).read_text(encoding="utf-8")
        lines = source.splitlines()
        imports = [
            line.strip()
            for line in lines
            if FORBIDDEN_REPOSITORY_IMPORT_MARKER in line
            and ".provider import" not in line
        ]
        assert imports == [], f"{filename} bypasses RepositoryProvider: {imports}"


def test_migrated_services_have_no_concrete_repository_construction():
    for filename in sorted(MIGRATED_SERVICES):
        source = (SERVICES_DIR / filename).read_text(encoding="utf-8")
        constructions = [
            line.strip()
            for line in source.splitlines()
            if FORBIDDEN_REPOSITORY_CONSTRUCTION_MARKER in line
            and "RepositoryProvider(" not in line
        ]
        assert constructions == [], (
            f"{filename} directly constructs a repository: {constructions}"
        )
