from pathlib import Path


SERVICE = Path(__file__).parents[1] / "src" / "centermanager" / "services" / "enrollment_service.py"
INVENTORY = Path(__file__).parents[1] / "docs" / "architecture" / "EP-ARCH-03_SERVICE_INVENTORY.md"


def test_enrollment_service_uses_repository_provider_and_repository_owned_refresh():
    source = SERVICE.read_text(encoding="utf-8")
    assert "RepositoryProvider" in source
    assert "self._repository_provider.enrollments(session)" in source
    assert "session.query(" not in source
    assert "session.add(" not in source
    assert "session.delete(" not in source
    assert "session.refresh(" not in source
    assert "repo.refresh(enrollment)" in source


def test_batch_d_inventory_records_enrollment_service_as_provider_backed():
    source = INVENTORY.read_text(encoding="utf-8")
    assert "`enrollment_service.py` | PASS" in source
    assert "**EnrollmentService**" in source
    assert "RepositoryProvider.enrollments(...)" in source
