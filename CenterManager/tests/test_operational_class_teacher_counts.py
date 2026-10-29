"""Regression: operational counts exclude withdrawn and historical contracts."""
from centermanager.models.class_ import Class
from centermanager.models.enrollment import Enrollment


def _enrollment(status, reconciled=None):
    return Enrollment(
        student_id=1,
        status=status,
        reconciled_into_enrollment_id=reconciled,
    )


def test_class_student_count_excludes_historical_and_reconciled_enrollments():
    clazz = Class(name="K1_Robotics", capacity=4)
    clazz.enrollments = [
        _enrollment("ACTIVE"),
        _enrollment("ACTIVE"),
        _enrollment("ACTIVE"),
        _enrollment("WITHDRAWN"),
        _enrollment("COMPLETED"),
        _enrollment("ACTIVE", reconciled=12),
    ]
    assert clazz.student_count == 3
    assert not clazz.is_full
    clazz.capacity = 3
    assert clazz.is_full


def test_teacher_dashboard_assignment_count_excludes_archived_classes():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1]
        / "src/centermanager/ui/teacher_workspace/teacher_dashboard_page.py"
    ).read_text(encoding="utf-8")
    assert "for assigned_class in teacher.assigned_classes" in source
    assert "if assigned_class.deleted_at is None" in source


def test_class_list_and_detail_reuse_active_count():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src/centermanager/ui/class_workspace"
    assert "class_obj.student_count" in (root / "class_detail_page.py").read_text(encoding="utf-8")
    assert "c.student_count" in (root / "class_list_page.py").read_text(encoding="utf-8")
