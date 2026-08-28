from pathlib import Path
GEN = Path("src/centermanager/export/pdf/student_report_generator.py").read_text(encoding="utf-8")
DETAIL = Path("src/centermanager/ui/student_workspace/student_detail_page.py").read_text(encoding="utf-8")
SERVICE = Path("src/centermanager/services/student_service.py").read_text(encoding="utf-8")
TX = Path("src/centermanager/services/write_transaction.py").read_text(encoding="utf-8")
REPORT = Path("src/centermanager/services/report_service.py").read_text(encoding="utf-8")

def test_27_manual_export_is_read_only():
    start = DETAIL.index("def _export_pdf")
    end = DETAIL.find("\n    def ", start + 1)
    body = DETAIL[start:end]
    assert "ensure_write()" not in body
    assert "generate_student_report(" in body

def test_27_retry_publish_reuses_post_publish_callback():
    assert "self._on_publish_success" in TX
    assert "def retry_publish" in TX
    start = TX.index("def retry_publish")
    retry = TX[start:start + 1200]
    assert "self._on_publish_success = None" not in retry
    assert "return self._publish()" in retry

def test_27_student_policy_does_not_generate_pre_publish_report():
    start = SERVICE.index("def _trigger_report_policy")
    end = SERVICE.find("\n    def ", start + 1)
    body = SERVICE[start:end]
    assert "generation deferred to publish lifecycle" in body
    assert "generate_student_report(" not in body

def test_27_report_has_academic_enrollment_and_assessment_contract():
    for token in (
        "active_enrollments",
        "completed_enrollments",
        "withdrawn_enrollments",
        "TỔNG QUAN GHI DANH",
        "ĐÁNH GIÁ GẦN NHẤT",
        "latest_assessment",
    ):
        assert token in GEN

def test_27_report_removes_fake_student_contact_fields():
    assert '("Số điện thoại", "")' not in GEN
    assert '("Email", "")' not in GEN
    assert '("Địa chỉ", "")' not in GEN

def test_27_report_preserves_single_latest_artifact():
    assert 'output_path = reports_root / "StudentProfile.pdf"' in REPORT
    assert "for existing in repo.get_by_student(student_id):" in REPORT
