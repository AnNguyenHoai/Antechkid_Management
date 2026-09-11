from pathlib import Path

CLASS_SERVICE = Path("src/centermanager/services/class_service.py").read_text(encoding="utf-8")
SESSION_SERVICE = Path("src/centermanager/services/session_service.py").read_text(encoding="utf-8")
SHELL = Path("src/centermanager/ui/class_workspace/class_workspace_shell.py").read_text(encoding="utf-8")


def test_noop_class_update_does_not_emit_false_domain_event():
    assert """if not changes:
                return class_obj""" in CLASS_SERVICE


def test_session_delete_event_is_published_after_commit():
    start = SESSION_SERVICE.index("def delete_session(")
    block = SESSION_SERVICE[start:]
    assert block.index("db_session.commit()") < block.index('action="deleted"')


def test_workspace_navigation_and_header_are_not_double_connected():
    assert SHELL.count("self.nav.page_selected.connect(self.navigate_to)") == 1
    assert SHELL.count("self.header.back_home_clicked.connect(self.go_home.emit)") == 1


def test_final_audit_keeps_cross_page_event_contract():
    for token in (
        "ClassCreated",
        "ClassUpdated",
        "ClassArchived",
        "ClassRestored",
        "ClassSessionChanged",
        "StudentEnrollmentChanged",
        "TeacherAssignmentChanged",
    ):
        assert token in SHELL
