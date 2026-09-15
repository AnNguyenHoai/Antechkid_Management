from pathlib import Path

def test_profile_image_student_updated_includes_required_changes_field():
    source = Path("src/centermanager/services/student_service.py").read_text(encoding="utf-8")
    start = source.index("def set_profile_image")
    end = source.index("\n    def update_student", start)
    section = source[start:end]
    assert "changes=[\"profile_image_path\"]" in section
