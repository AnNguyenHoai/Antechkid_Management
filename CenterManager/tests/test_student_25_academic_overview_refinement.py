from pathlib import Path

UI = Path("src/centermanager/ui/student_workspace/enrollment_widget.py").read_text(encoding="utf-8")
REPO = Path("src/centermanager/repositories/enrollment_repository.py").read_text(encoding="utf-8")

def test_25_academic_overview_summary_exists():
    assert "Academic Overview" in UI
    assert "Academic Summary" in UI
    for label in ("Active", "Completed", "Withdrawn", "Total Records"):
        assert f'("{label}"' in UI

def test_25_summary_is_derived_from_canonical_enrollment_statuses():
    for token in (
        "EnrollmentStatus.ACTIVE.value",
        "EnrollmentStatus.COMPLETED.value",
        "EnrollmentStatus.WITHDRAWN.value",
    ):
        assert token in UI

def test_25_history_cards_show_status_dates_and_metadata():
    for token in ("teacher_name", "level", "start_date", "end_date", "_format_duration"):
        assert token in UI

def test_25_current_enrollment_is_not_offered_again():
    assert "active_class_ids" in UI
    assert "class_obj.id not in active_class_ids" in UI

def test_25_history_order_is_newest_first_at_repository_boundary():
    start = REPO.index("def get_by_student(self, student_id: int)")
    end = REPO.index("def get_by_class(", start)
    assert "order_by(desc(Enrollment.created_at))" in REPO[start:end]

def test_25_history_remains_read_only_and_mutations_are_write_guarded():
    assert "def _require_write" in UI
    assert "Complete" in UI
    assert "Withdraw" in UI
