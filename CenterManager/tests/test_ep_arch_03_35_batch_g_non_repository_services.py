"""EP-ARCH-03.35 Batch G — non-repository service classification contract."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs" / "architecture" / "EP-ARCH-03_SERVICE_INVENTORY.md"

EXPECTED_NON_REPOSITORY = {
    "authorization_service.py": "AuthorizationService",
    "auto_report_service.py": "AutoReportService",
    "backup_operations_service.py": "BackupOperationsService",
    "configuration_service.py": "ConfigurationService",
    "git_config_service.py": "GitConfigService",
    "system_operations_service.py": "SystemOperationsService",
}


def _row(source: str, service_name: str) -> str:
    start = source.index(f"`{service_name}`")
    return source[start : source.index("\n", start)]


def test_batch_g_services_are_explicitly_non_repository():
    source = INVENTORY.read_text(encoding="utf-8")
    for service_name in EXPECTED_NON_REPOSITORY:
        row = _row(source, service_name)
        assert "| NON_REPOSITORY |" in row, row


def test_batch_g_documents_service_boundary_reason():
    source = INVENTORY.read_text(encoding="utf-8")
    for service_name, class_name in EXPECTED_NON_REPOSITORY.items():
        assert f"`{service_name}`" in source
        assert f"**{class_name}**" in source
    assert "Batch G closes the false-positive legacy classification" in source
    assert "must not be forced to inject a `RepositoryProvider`" in source


def test_batch_g_does_not_reclassify_database_backed_legacy_services():
    source = INVENTORY.read_text(encoding="utf-8")
    # SessionService and TimelineService were subsequently migrated by EP-ARCH-03.37.
    # Keep only services that are still genuinely in the legacy backlog here.
    for service_name in (
        "teacher_service.py",
    ):
        row = _row(source, service_name)
        assert "| LEGACY |" in row, row

    for service_name in (
        "student_service.py",
        "income_service.py",
        "expense_service.py",
        "expense_timeline_service.py",
        "session_service.py",
        "timeline_service.py",
    ):
        row = _row(source, service_name)
        assert "| PASS |" in row, row
