from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations" / "versions" / "1e10a016_runtime_employee_registration_repairs.py"


def test_runtime_repair_migration_has_unique_head_and_teacher_self_permission():
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "1e10a016"' in source
    assert 'down_revision = "1e10a015"' in source
    assert 'SELF_PERMISSION = "work_registration.self"' in source
    assert 'TEACHER_ROLE = "teacher"' in source
    assert 'INSERT OR IGNORE INTO role_permissions' in source


def test_runtime_repair_migration_repairs_employee_document_foreign_key():
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'employee_documents' in source
    assert 'ondelete="CASCADE"' in source
    assert 'drop_constraint(' in source
    assert 'create_foreign_key(' in source
