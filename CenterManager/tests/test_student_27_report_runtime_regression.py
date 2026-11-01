from pathlib import Path

SERVICE = Path("src/centermanager/services/student_service.py").read_text(encoding="utf-8")
REPOSITORY = Path("src/centermanager/repositories/student_repository.py").read_text(encoding="utf-8")
GENERATOR = Path("src/centermanager/export/pdf/student_report_generator.py").read_text(encoding="utf-8")
MAIN = Path("src/centermanager/ui/main_window.py").read_text(encoding="utf-8")

def test_student_27_update_student_publishes_student_updated_after_commit():
    start = SERVICE.index("def update_student")
    end = SERVICE.index("\n    def delete_student", start)
    body = SERVICE[start:end]
    assert "session.commit()" in body
    assert "self._event_bus.publish(StudentUpdated(" in body
    assert body.index("session.commit()") < body.index("self._event_bus.publish(StudentUpdated(")

def test_student_27_report_query_eager_loads_assessments():
    start = REPOSITORY.index("def get_with_relations")
    body = REPOSITORY[start:]
    assert "selectinload(Student.assessments)" in body

def test_student_27_derived_reports_use_dirty_student_ids():
    tx = Path("src/centermanager/services/write_transaction.py").read_text(encoding="utf-8")
    assert "self._generate_reports(set(self._dirty_student_ids))" in tx
    callback = MAIN[MAIN.index('def on_publish_success():'):MAIN.index('def on_publish_failure')]
    assert 'generate_student_report' not in callback

def test_student_27_generator_reads_loaded_assessments():
    assert 'getattr(student, "assessments", None)' in GENERATOR
