from pathlib import Path

TX = Path("src/centermanager/services/write_transaction.py").read_text(encoding="utf-8")
MAIN = Path("src/centermanager/ui/main_window.py").read_text(encoding="utf-8")
DETAIL = Path("src/centermanager/ui/student_workspace/student_detail_page.py").read_text(encoding="utf-8")
SHELL = Path("src/centermanager/ui/student_workspace/student_workspace_shell.py").read_text(encoding="utf-8")
SERVICE = Path("src/centermanager/services/enrollment_service.py").read_text(encoding="utf-8")
REPORT = Path("src/centermanager/services/report_service.py").read_text(encoding="utf-8")
EVENTS = Path("src/centermanager/events/student_events.py").read_text(encoding="utf-8")

def test_24_event_is_published_only_after_database_commit():
    enroll_start = SERVICE.index("def enroll(")
    transition_start = SERVICE.index("def _transition(", enroll_start)
    enroll_section = SERVICE[enroll_start:transition_start]
    enroll_commit = enroll_section.index("session.commit()")
    enroll_refresh = enroll_section.index("repo.refresh(enrollment)")
    enroll_event = enroll_section.index('self._publish_change(enrollment, "ENROLLED", None)')
    assert enroll_commit < enroll_refresh < enroll_event

    transition_end = SERVICE.index("def get_student_history(", transition_start)
    transition_section = SERVICE[transition_start:transition_end]
    transition_commit = transition_section.index("session.commit()")
    transition_refresh = transition_section.index("repo.refresh(enrollment)")
    transition_event = transition_section.index("self._publish_change(")
    assert transition_commit < transition_refresh < transition_event

def test_24_enrollment_event_tracks_owning_student_aggregate():
    start = MAIN.index("def _on_student_enrollment_changed_event")
    end = MAIN.index("def _on_student_deleted_event", start)
    section = MAIN[start:end]
    assert "self._transaction.is_editing" in section
    assert "self._transaction.mark_student_dirty(event.student_id)" in section

def test_24_report_preparation_captures_dirty_ids_before_transaction_reset():
    publish = TX.index("if self._on_publish_success:")
    reset = TX.index("self._reset_to_idle()", publish)
    assert publish < reset
    assert "self._prepare_reports(set(self._dirty_student_ids))" in TX
    assert TX.index("self._prepare_reports(set(self._dirty_student_ids))") < TX.index("if not self._publish_database_and_manifest():")

def test_24_report_generation_is_pre_publish_and_one_per_dirty_student():
    assert 'for student_id in sorted(set(student_ids)):' in REPORT
    assert 'self._generate(student_id, "latest", "student_updated", "system", None,' in REPORT
    assert 'persist_metadata=True' in REPORT

def test_24_failed_publish_keeps_prepared_reports_unaccepted():
    publish = TX[TX.index('def _publish(self)'):TX.index('def _do_publish')]
    success = publish[publish.index('if success:'):publish.index('else:')]
    assert 'self._verify_reports()' in success
    failure = publish[publish.index('else:'):]
    assert '_verify_reports()' not in failure
    assert '_delete_snapshot()' not in failure

def test_24_synced_runtime_reloads_current_student_and_enrollment_surface():
    assert "self.student_workspace.refresh_current_student()" in MAIN
    shell_refresh = SHELL[SHELL.index("def refresh_current_student"):SHELL.index("@property", SHELL.index("def refresh_current_student"))]
    assert "self.detail_page.load_student(self._current_student_id)" in shell_refresh
    assert "self.enrollment_widget.set_student(student.id)" in DETAIL

def test_24_reload_required_refreshes_student_workspace():
    start = MAIN.index("def _on_reload_required_ui")
    section = MAIN[start:MAIN.index("def ", start + 10)]
    assert "self.student_workspace.refresh()" in section
    assert "self.student_workspace.refresh_current_student()" in section

def test_24_event_payload_contains_status_and_aggregate_identity():
    for field in ("student_id", "enrollment_id", "class_id", "action", "previous_status", "current_status"):
        assert field in EVENTS

def test_24_terminal_enrollment_mutations_still_preserve_history():
    assert "EnrollmentStatus.COMPLETED" in SERVICE
    assert "EnrollmentStatus.WITHDRAWN" in SERVICE
    assert "self._session.delete" not in SERVICE
