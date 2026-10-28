"""Archive Class UX safety contracts: warn about preserved liabilities and dependencies."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVICE = ROOT / "src/centermanager/services/class_service.py"
PAGE = ROOT / "src/centermanager/ui/class_workspace/class_list_page.py"


def test_archive_preview_is_read_only_and_uses_dependency_snapshot():
    source = SERVICE.read_text(encoding="utf-8")
    start = source.index("    def preview_archive_class(")
    end = source.index("    def archive_class(", start)
    preview = source[start:end]
    assert "self._archive_snapshot(session, class_id)" in preview
    assert "session.commit()" not in preview
    assert "deleted_at =" not in preview


def test_archive_confirmation_discloses_enrollment_and_finance_consequences():
    source = PAGE.read_text(encoding="utf-8")
    assert "preview_archive_class(class_id)" in source
    assert "Active enrollments will NOT be completed" in source
    assert "Outstanding tuition is NOT settled" in source
    assert "preview_archive_class(cid)" in source
    assert "Restore each class before changing its enrollments." in source
