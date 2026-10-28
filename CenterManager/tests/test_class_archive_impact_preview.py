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
    assert "Active enrollments WILL be withdrawn" in source
    assert "Outstanding tuition remains collectible" in source
    assert "preview_archive_class(cid)" in source
    assert "Restore each class before changing its enrollments." in source


def test_class_archive_applies_withdrawals_and_soft_archive_in_one_commit():
    source = SERVICE.read_text(encoding="utf-8")
    start = source.index("    def archive_class(")
    end = source.index("    def restore_class(", start)
    body = source[start:end]
    assert 'enrollment.status = "WITHDRAWN"' in body
    assert "enrollment.withdrawn_from_session" in body
    assert "enrollment.end_date = withdrawal_date" in body
    assert body.index('enrollment.status = "WITHDRAWN"') < body.index("class_obj.deleted_at =")
    assert body.count("session.commit()") == 1
    assert "enrollment.has_open_freeze" in body


def test_archive_finance_quote_does_not_mutate_enrollment_and_is_rechecked():
    source = SERVICE.read_text(encoding="utf-8")
    assert "class WithdrawalProjection:" in source
    assert "current.outstanding" in source
    assert "projected.outstanding" in source
    assert "expected_finance_impact" in source
    assert "latest_impact != expected_finance_impact" in source
    page = PAGE.read_text(encoding="utf-8")
    assert "Outstanding before:" in page
    assert "Outstanding after:" in page
    assert "Difference:" in page
    assert "expected_finance_impact={" in page
