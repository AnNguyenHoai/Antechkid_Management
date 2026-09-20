from datetime import date
from pathlib import Path
from types import SimpleNamespace

from centermanager.services.attendance_service import AttendanceService


ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = ROOT / "src" / "centermanager" / "services" / "attendance_service.py"
UI_PATH = ROOT / "src" / "centermanager" / "ui" / "session" / "session_attendance_widget.py"
SCHEDULE_PATH = ROOT / "src" / "centermanager" / "ui" / "class_workspace" / "class_schedule_widget.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_att_02_enrollment_window_is_session_date_aware():
    service = AttendanceService.__new__(AttendanceService)
    enrollment = SimpleNamespace(
        start_date=date(2026, 1, 5),
        end_date=date(2026, 1, 20),
    )

    assert service._enrollment_covers_session_date(enrollment, date(2026, 1, 5)) is True
    assert service._enrollment_covers_session_date(enrollment, date(2026, 1, 15)) is True
    assert service._enrollment_covers_session_date(enrollment, date(2026, 1, 20)) is True
    assert service._enrollment_covers_session_date(enrollment, date(2026, 1, 4)) is False
    assert service._enrollment_covers_session_date(enrollment, date(2026, 1, 21)) is False


def test_att_02_historical_enrollment_is_used_before_legacy_active_fallback():
    service = AttendanceService.__new__(AttendanceService)

    class HistoricalRepo:
        def __init__(self):
            self.exists_called = False

        def get_by_student_and_class(self, student_id, class_id):
            assert (student_id, class_id) == (7, 55)
            return [
                SimpleNamespace(
                    start_date=date(2026, 1, 1),
                    end_date=date(2026, 2, 1),
                    status="WITHDRAWN",
                )
            ]

        def exists(self, student_id, class_id):
            self.exists_called = True
            return False

    repo = HistoricalRepo()
    assert service._is_student_eligible_for_session(
        repo,
        7,
        55,
        date(2026, 1, 15),
    ) is True
    assert repo.exists_called is False


def test_att_02_legacy_injected_enrollment_provider_remains_compatible():
    service = AttendanceService.__new__(AttendanceService)

    class LegacyRepo:
        def exists(self, student_id, class_id):
            return student_id == 7 and class_id == 55

    repo = LegacyRepo()
    assert service._is_student_eligible_for_session(repo, 7, 55, None) is True
    assert service._is_student_eligible_for_session(repo, 8, 55, None) is False


def test_att_02_session_ui_uses_service_owned_historical_roster():
    service = _source(SERVICE_PATH)
    ui = _source(UI_PATH)

    assert "def get_roster_for_session" in service
    assert "get_by_class_with_student" in service
    assert "_enrollment_covers_session_date" in service
    assert "get_roster_for_session(self._session_id)" in ui
    assert "get_class_with_details(self._class_id)" not in ui


def test_att_02_attendance_mutation_fails_closed_without_write_authority():
    ui = _source(UI_PATH)
    schedule = _source(SCHEDULE_PATH)

    assert "self._write_guard: Optional[Callable[[], bool]] = None" in ui
    assert "def _can_write" in ui
    assert "if self._write_guard is None:" in ui
    assert "if not self._can_write():" in ui
    assert "self.save_btn.setEnabled(enabled)" in ui
    assert "self.mark_all_btn.setEnabled(enabled)" in ui
    assert "dialog.attendance_widget.set_write_guard" in schedule
    assert "self._collaboration_manager.ensure_write" in schedule


def test_att_02_keeps_session_as_attendance_owner_and_no_parallel_workspace():
    ui = _source(UI_PATH)
    schedule = _source(SCHEDULE_PATH)

    assert "save_session_attendance" in ui
    assert "SessionDetailDialog" in schedule
    assert "AttendanceWorkspace" not in ui
    assert "AttendanceWorkspace" not in schedule
