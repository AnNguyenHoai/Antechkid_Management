from pathlib import Path
F=Path("src/centermanager/services/student_filter_service.py").read_text(encoding="utf-8")
L=Path("src/centermanager/ui/student_workspace/student_list_page.py").read_text(encoding="utf-8")
R=Path("src/centermanager/services/report_service.py").read_text(encoding="utf-8")
T=Path("src/centermanager/services/write_transaction.py").read_text(encoding="utf-8")
M=Path("src/centermanager/ui/main_window.py").read_text(encoding="utf-8")
P=Path("src/centermanager/export/pdf/student_report_generator.py").read_text(encoding="utf-8")
SR=Path("src/centermanager/repositories/student_repository.py").read_text(encoding="utf-8")

def test_archived_filter_uses_status(): assert 'Student.status == "ARCHIVED"' in SR
def test_ui_preserves_filter_base():
    assert "self._filtered_base" in L
    assert "self._filter_service.filter_students(filter_criteria)" in L
    assert "self._advanced_filter_active = True" in L
def test_latest_report_singleton_and_atomic():
    assert '"StudentProfile.pdf"' in R
    assert '_install(temporary, destination)' in R
    assert 'os.fsync(stream.fileno())' in R

def test_dirty_students_track_transaction(): assert 'mark_student_dirty' in T and 'dirty_student_ids' in T
def test_reports_prepared_before_publish_without_post_publish_sql():
    assert 'self._prepare_reports(set(self._dirty_student_ids))' in T
    section = M[M.index('def on_publish_success():'):M.index('def on_publish_failure')]
    assert 'generate_student_report' not in section

def test_profile_image_is_embedded_when_available(): assert 'profile_image_path' in P and 'Image(str(image_path)' in P