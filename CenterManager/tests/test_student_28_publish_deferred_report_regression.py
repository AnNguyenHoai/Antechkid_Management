from pathlib import Path
ATTENDANCE = Path("src/centermanager/services/attendance_service.py").read_text(encoding="utf-8")
AUTO = Path("src/centermanager/services/auto_report_service.py").read_text(encoding="utf-8")
REPORT = Path("src/centermanager/services/report_service.py").read_text(encoding="utf-8")

def test_attendance_defers_generation_to_publish_lifecycle():
    start = ATTENDANCE.index("def create_or_update_attendance")
    end = ATTENDANCE.index("\n    def _trigger_report_policy", start)
    body = ATTENDANCE[start:end]
    assert "StudentUpdated(" in body
    assert "generate_student_report(" not in body

def test_daily_auto_report_is_date_aware_and_retry_safe():
    assert "report_exists_on_date" in AUTO
    assert "completion state was not advanced" in AUTO
    assert 'and self._report_service.report_exists(student.id, "daily")' not in AUTO

def test_report_service_has_date_aware_contract():
    assert "def report_exists_on_date" in REPORT
