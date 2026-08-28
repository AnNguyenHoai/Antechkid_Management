from pathlib import Path

SERVICE = Path("src/centermanager/services/student_service.py").read_text(encoding="utf-8")
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
    start = SERVICE.index("def get_student_with_relations")
    body = SERVICE[start:]
    assert "selectinload(Student.assessments)" in body

def test_student_27_post_publish_uses_dirty_student_ids():
    assert "dirty_student_ids = list(self._transaction.dirty_student_ids)" in MAIN
    assert "self._report_service.generate_student_report(" in MAIN

def test_student_27_generator_reads_loaded_assessments():
    assert 'getattr(student, "assessments", None)' in GENERATOR
