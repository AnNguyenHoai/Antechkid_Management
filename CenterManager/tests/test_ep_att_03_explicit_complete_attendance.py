from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = ROOT / "src" / "centermanager" / "services" / "attendance_service.py"
UI_PATH = ROOT / "src" / "centermanager" / "ui" / "session" / "session_attendance_widget.py"
DETAIL_PATH = ROOT / "src" / "centermanager" / "ui" / "session" / "session_detail_dialog.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_att_03_unrecorded_rows_are_not_pre_marked_present():
    ui = _source(UI_PATH)
    assert 'UNMARKED_STATUS = "Not Marked"' in ui
    assert "combo.addItem(self.UNMARKED_STATUS)" in ui
    assert "combo.setCurrentIndex(0)  # Present" not in ui


def test_att_03_ui_requires_every_roster_student_to_be_explicitly_marked():
    ui = _source(UI_PATH)
    assert "unmarked_students = [" in ui
    assert "combo.currentText() == self.UNMARKED_STATUS" in ui
    assert '"Incomplete Attendance"' in ui
    save_source = ui.split("def _save_attendance", 1)[1].split("def refresh", 1)[0]
    assert "if unmarked_students:" in save_source
    assert "return" in save_source.split("if unmarked_students:", 1)[1].split("attendance_rows = {}", 1)[0]


def test_att_03_canonical_sheet_service_requires_exact_roster_but_legacy_batch_stays_compatible():
    service = _source(SERVICE_PATH)
    save_source = service.split("def save_session_attendance", 1)[1].split(
        '@require_permission("attendance.create")\n    def batch_update_attendance', 1
    )[0]
    batch_source = service.split("def batch_update_attendance", 1)[1].split(
        "def _get_roster_for_session", 1
    )[0]
    assert "_get_roster_for_session" in save_source
    assert "payload_ids != roster_ids" in save_source
    assert "_save_session_attendance_atomic" in save_source
    assert "_get_roster_for_session" not in batch_source
    assert "_save_session_attendance_atomic" in batch_source


def test_att_03_both_session_surfaces_use_one_roster_aware_overview_contract():
    service = _source(SERVICE_PATH)
    ui = _source(UI_PATH)
    detail = _source(DETAIL_PATH)
    assert "def get_session_attendance_overview" in service
    assert '"RosterTotal"' in service
    assert '"Unmarked"' in service
    assert '"AttendanceRate"' in service
    assert "get_session_attendance_overview(self._session_id)" in ui
    assert "get_session_attendance_overview(self._session_id)" in detail
    assert "total = sum(summary.values())" not in detail


def test_att_03_preserves_existing_attendance_status_domain():
    service = _source(SERVICE_PATH)
    ui = _source(UI_PATH)
    assert "AttendanceStatus.PRESENT.value" in service
    assert "AttendanceStatus.choices()" in ui
    assert "Not Marked" in ui
    # UI sentinel is not a persisted domain status: service validation remains authoritative.
    assert 'self._validate_status(str(raw.get("status", "")))' in service
