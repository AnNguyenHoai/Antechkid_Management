from pathlib import Path

TX = Path("src/centermanager/services/write_transaction.py").read_text(encoding="utf-8")
MAIN = Path("src/centermanager/ui/main_window.py").read_text(encoding="utf-8")
DETAIL = Path("src/centermanager/ui/student_workspace/student_detail_page.py").read_text(encoding="utf-8")
SHELL = Path("src/centermanager/ui/student_workspace/student_workspace_shell.py").read_text(encoding="utf-8")
SERVICE = Path("src/centermanager/services/enrollment_service.py").read_text(encoding="utf-8")
EVENTS = Path("src/centermanager/events/student_events.py").read_text(encoding="utf-8")

def test_24_event_is_published_only_after_database_commit():
    enroll_commit = SERVICE.index("session.commit(); session.refresh(enrollment)")
    enroll_event = SERVICE.index('self._publish_change(enrollment, "ENROLLED", None)')
    assert enroll_commit < enroll_event

    transition_commit = SERVICE.index("session.commit(); session.refresh(enrollment)", enroll_commit + 1)
    transition_event = SERVICE.index("self._publish_change(", transition_commit)
    assert transition_commit < transition_event

def test_24_enrollment_event_tracks_owning_student_aggregate():
    start = MAIN.index("def _on_student_enrollment_changed_event")
    end = MAIN.index("def _on_student_deleted_event", start)
    section = MAIN[start:end]
    assert "self._transaction.is_editing" in section
    assert "self._transaction.mark_student_dirty(event.student_id)" in section

def test_24_publish_callback_captures_dirty_ids_before_transaction_reset():
    publish = TX.index("if self._on_publish_success:")
    reset = TX.index("self._reset_to_idle()", publish)
    assert publish < reset

    callback = MAIN.index("def on_publish_success():")
    report_loop = MAIN.index("for student_id in dirty_student_ids:", callback)
    assert callback < report_loop
    assert "dirty_student_ids = list(self._transaction.dirty_student_ids)" in MAIN[callback:report_loop]

def test_24_report_generation_is_post_publish_and_one_per_dirty_student():
    callback = MAIN.index("def on_publish_success():")
    finish_call = MAIN.index("success = self._transaction.finish_editing(")
    section = MAIN[callback:finish_call]
    assert "for student_id in dirty_student_ids:" in section
    assert 'report_type="latest"' in section
    assert 'trigger_event="student_updated"' in section
    assert "except Exception:" in section

def test_24_failed_publish_does_not_generate_report():
    callback = MAIN.index("def on_publish_success():")
    failure = MAIN.index("def on_publish_failure", callback)
    section = MAIN[callback:failure]
    assert "generate_student_report" in section
    assert MAIN.index("generate_student_report", callback) < failure

    publish = TX.index("if success:")
    failure_branch = TX.index("else:", publish)
    assert TX.index("_on_publish_success()", publish) < failure_branch

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
