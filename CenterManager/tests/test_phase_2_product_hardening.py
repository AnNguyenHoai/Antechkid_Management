"""Regression contracts for the consolidated Phase 2 hardening pass."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "centermanager"
DOCS = ROOT / "docs"


def read(rel: str) -> str:
    return (SRC / rel).read_text(encoding="utf-8")


def test_hardening_contract_covers_all_phase_2_surfaces():
    doc = (DOCS / "PHASE_2_PRODUCT_HARDENING.md").read_text(encoding="utf-8")
    for phrase in (
        "Domain/data integrity",
        "Permission and mutation boundaries",
        "Error/recovery contracts",
        "Cross-workspace operational workflow consistency",
        "Reporting/export source-of-truth consistency",
        "Performance baseline contracts",
        "Backup/restore and deployment readiness",
    ):
        assert phrase in doc


def test_soft_delete_apis_preserve_historical_student_and_class_records():
    student = read("services/student_service.py")
    clazz = read("services/class_service.py")
    assert "student.deleted_at = self._utc_now()" in student
    assert "repo.get_by_id_including_deleted(student_id)" in student
    assert "class_obj.deleted_at = self._utc_now()" in clazz
    assert "list_archived_classes" in clazz
    # The class service archives the aggregate instead of deleting its related
    # records; the dependency snapshot is retained in the archive timeline.
    assert "snapshot = self._archive_snapshot(session, class_id)" in clazz
    assert 'metadata={"dependency_snapshot": snapshot}' in clazz
    assert "teacher assignments" in clazz
    assert "enrollments" in clazz
    assert "sessions" in clazz


def test_database_integrity_and_transaction_boundaries_are_explicit():
    engine = read("database/engine.py")
    session = read("database/session.py")
    migration = read("database/migration.py")
    assert "PRAGMA foreign_keys = ON" in engine
    assert "session.commit()" in session and "session.rollback()" in session and "session.close()" in session
    assert "command.upgrade(config, \"head\")" in migration
    assert "validate_database_at_head" in migration


def test_authorization_has_single_capability_entry_point():
    auth = read("services/authorization_service.py")
    capabilities = read("core/capabilities.py")
    assert "class AuthorizationService" in auth
    assert "def require(" in auth
    assert "class Capability" in capabilities
    assert "ADMIN_ONLY_CAPABILITIES" in capabilities


def test_backup_restore_has_integrity_and_managed_path_guards():
    backup = read("platform/backup/backup_service.py")
    operations = read("services/backup_operations_service.py")
    hardening = read("services/product_hardening_service.py")
    assert "PRAGMA integrity_check" in backup
    assert "Database checksum mismatch" in backup
    assert "Backup path is outside the managed backup directory" in backup
    assert "pre_restore" in operations
    assert "def require_managed_path" in hardening


def test_hardening_service_reuses_canonical_authorization():
    source = read("services/product_hardening_service.py")
    tree = ast.parse(source)
    imports = [node for node in tree.body if isinstance(node, ast.ImportFrom)]
    assert any(node.module == "centermanager.services.authorization_service" for node in imports)
    assert any(node.module == "centermanager.core.capabilities" for node in imports)
