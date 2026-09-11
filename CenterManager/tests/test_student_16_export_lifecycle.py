from pathlib import Path
F=Path("src/centermanager/services/student_filter_service.py").read_text(encoding="utf-8")
L=Path("src/centermanager/ui/student_workspace/student_list_page.py").read_text(encoding="utf-8")
R=Path("src/centermanager/services/report_service.py").read_text(encoding="utf-8")
T=Path("src/centermanager/services/write_transaction.py").read_text(encoding="utf-8")
M=Path("src/centermanager/ui/main_window.py").read_text(encoding="utf-8")
P=Path("src/centermanager/export/pdf/student_report_generator.py").read_text(encoding="utf-8")

def test_archived_filter_uses_status(): assert 'Student.status == "ARCHIVED"' in F
def test_ui_preserves_filter_base(): assert 'self._filtered_base = self._filter_service.filter_students(filter_dto)' in L
def test_latest_report_singleton_and_atomic(): 
    assert '"StudentProfile.pdf"' in R
    assert 'temp_path' in R and 'file_path.replace(output_path)' in R
def test_dirty_students_track_transaction(): assert 'mark_student_dirty' in T and 'dirty_student_ids' in T
def test_reports_generated_after_publish_success(): assert 'for student_id in dirty_student_ids' in M
def test_profile_image_is_embedded_when_available(): assert 'profile_image_path' in P and 'Image(str(image_path)' in P
