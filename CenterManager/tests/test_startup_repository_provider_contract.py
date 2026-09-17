from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_student_note_service_has_safe_production_provider_fallback():
    source = (ROOT / "src/centermanager/services/student_note_service.py").read_text(encoding="utf-8")
    assert "create_default_repository_provider" in source
    assert "repository_provider or create_default_repository_provider()" in source
    assert "self._repository_provider" in source
