from pathlib import Path

DOC = Path("src/centermanager/ui/student_workspace/documents_widget.py").read_text(encoding="utf-8")
DETAIL = Path("src/centermanager/ui/student_workspace/student_detail_page.py").read_text(encoding="utf-8")
REPORTS = Path("src/centermanager/ui/student_workspace/report_list_widget.py").read_text(encoding="utf-8")

def test_document_widget_uses_loaded_student_identity_not_new_production_engine():
    assert "self._student_code" in DOC
    assert "create_production_engine" not in DOC

def test_document_write_mode_covers_upload_and_existing_delete_controls():
    assert "self.upload_btn.setEnabled(enabled)" in DOC
    assert "card.delete_btn.setEnabled(enabled)" in DOC

def test_detail_passes_student_code_to_documents():
    assert "self.documents_widget.set_student(student.id, student.student_code)" in DETAIL

def test_report_generation_requires_write_mode():
    start = DETAIL.index("def _export_pdf")
    body = DETAIL[start:start+700]
    assert "ensure_write()" in body

def test_report_list_supports_write_guarded_delete_and_refresh():
    assert "report_changed = Signal()" in REPORTS
    assert "delete_btn.setEnabled(self._write_enabled)" in REPORTS
    assert "self._service.delete_report(report_id)" in REPORTS
    assert "self.report_changed.emit()" in REPORTS

def test_detail_refreshes_after_report_delete():
    assert "self.report_list_widget.report_changed.connect(self._on_data_changed)" in DETAIL
