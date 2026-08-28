from pathlib import Path

MAIN = Path("src/centermanager/ui/main_window.py").read_text(encoding="utf-8")
DETAIL = Path("src/centermanager/ui/student_workspace/student_detail_page.py").read_text(encoding="utf-8")
AUTO = Path("src/centermanager/services/auto_report_service.py").read_text(encoding="utf-8")
POLICY = Path("src/centermanager/services/report_policy.py").read_text(encoding="utf-8")
GEN = Path("src/centermanager/export/pdf/student_report_generator.py").read_text(encoding="utf-8")
SERVICE = Path("src/centermanager/services/report_service.py").read_text(encoding="utf-8")
DOC = Path("docs/STUDENT_2_6_STUDENT_REPORT_DATA_CONTRACT_AUDIT.md").read_text(encoding="utf-8")

def test_26_audit_records_all_current_report_trigger_sources():
    for source in (
        "Student Workspace publish",
        "Manual export",
        "Student ReportPolicy",
        "Attendance/session policy",
        "Daily auto report",
    ):
        assert source in DOC

def test_26_publish_is_post_success_and_uses_dirty_student_ids():
    assert "dirty_student_ids = list(self._transaction.dirty_student_ids)" in MAIN
    assert "def on_publish_success():" in MAIN
    assert 'report_type="latest"' in MAIN

def test_26_manual_export_is_an_explicit_report_trigger():
    assert "def _export_pdf(self)" in DETAIL
    assert "generate_student_report(" in DETAIL
    assert 'report_type="manual"' in DETAIL

def test_26_policy_has_student_and_progress_trigger_families():
    for token in ("student_updated", "attendance_updated", "session_completed", "progress_50", "progress_100"):
        assert token in POLICY

def test_26_daily_auto_report_is_a_separate_current_trigger():
    assert "generate_student_report(" in AUTO
    assert 'trigger_event="daily"' in AUTO

def test_26_report_is_singleton_latest_artifact():
    assert 'output_path = reports_root / "StudentProfile.pdf"' in SERVICE
    assert "for existing in repo.get_by_student(student_id):" in SERVICE

def test_26_current_report_data_sections_are_explicitly_audited():
    for section in (
        "THÔNG TIN HỌC SINH",
        "TÌNH HÌNH HỌC TẬP",
        "THÔNG TIN HỌC PHÍ",
        "ĐIỂM DANH GẦN ĐÂY",
        "NHẬN XÉT CỦA GIÁO VIÊN",
    ):
        assert section in GEN

def test_26_known_data_gaps_are_documented():
    for gap in (
        "Student phone/email/address fields are rendered as empty constants",
        "Enrollment lifecycle history is not represented",
        "Assessment is absent",
        "Multiple parents are collapsed to one primary parent",
    ):
        assert gap in DOC
