from pathlib import Path

LIST = Path("src/centermanager/ui/teacher_workspace/teacher_list_page.py").read_text(encoding="utf-8")
DASHBOARD = Path("src/centermanager/ui/teacher_workspace/teacher_dashboard_page.py").read_text(encoding="utf-8")
TIMELINE_SERVICE = Path("src/centermanager/services/teacher_timeline_service.py").read_text(encoding="utf-8")
TIMELINE_REPOSITORY = Path("src/centermanager/repositories/teacher_timeline_repository.py").read_text(encoding="utf-8")


def test_recent_activity_is_loaded_globally_not_per_teacher():
    start = DASHBOARD.index("def _refresh_recent_activities")
    body = DASHBOARD[start:]
    assert "self._timeline_service.get_recent_events(limit=10)" in body
    assert "for t in teachers:" not in body
    assert "get_teacher_timeline(t.id" not in body


def test_dashboard_activity_service_has_explicit_global_query():
    assert "def get_recent_events(self, limit: int = 10)" in TIMELINE_SERVICE
    assert "repo.get_recent_events(limit=limit)" in TIMELINE_SERVICE


def test_timeline_repository_orders_global_activity_and_limits_result():
    assert "def get_recent_events(self, limit: int = 10)" in TIMELINE_REPOSITORY
    assert "desc(TeacherTimelineEvent.created_at)" in TIMELINE_REPOSITORY
    assert ".limit(limit).all()" in TIMELINE_REPOSITORY


def test_dashboard_assignment_kpi_avoids_one_service_call_per_teacher():
    start = DASHBOARD.index("def refresh")
    end = DASHBOARD.index("def _refresh_recent_activities", start)
    body = DASHBOARD[start:end]
    assert "sum(len(t.assigned_classes) for t in teachers)" in body
    assert "get_assigned_classes(t.id)" not in body


def test_activity_card_keeps_teacher_context_from_event_relationship():
    start = DASHBOARD.index("def _refresh_recent_activities")
    body = DASHBOARD[start:]
    assert "ev.teacher.full_name" in body
    assert "Teacher #{ev.teacher_id}" in body


def test_recent_activity_eager_loads_teacher_before_service_session_closes():
    assert "joinedload(TeacherTimelineEvent.teacher)" in TIMELINE_REPOSITORY
    start = TIMELINE_REPOSITORY.index("def get_recent_events")
    end = TIMELINE_REPOSITORY.index("def add(", start)
    body = TIMELINE_REPOSITORY[start:end]
    assert ".options(joinedload(TeacherTimelineEvent.teacher))" in body


def test_teacher_list_imports_qcombobox_for_status_and_assignment_filters():
    assert "QComboBox" in LIST.split(")", 1)[0]
