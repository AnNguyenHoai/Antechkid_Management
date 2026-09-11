from pathlib import Path

SERVICE = Path("src/centermanager/services/session_report_service.py").read_text(encoding="utf-8")
WIDGET = Path("src/centermanager/ui/class_workspace/class_schedule_widget.py").read_text(encoding="utf-8")


def test_reports_are_grouped_by_class_and_lesson():
    assert 'f"Class_{class_obj.id}_{class_obj.name}"' in SERVICE
    assert 'f"Lesson_{session.session_number}_{lesson_title}"' in SERVICE
    assert 'get_paths().session_report_dir' in SERVICE
    assert '/ class_name' in SERVICE
    assert '/ lesson_name' in SERVICE
    assert '/ "latest.pdf"' in SERVICE


def test_folder_names_are_sanitized():
    assert "def _safe_folder_name" in SERVICE
    assert "re.sub" in SERVICE


def test_success_dialog_offers_open_save_location():
    assert "def _show_export_success_dialog" in WIDGET
    assert '"Open Save Location"' in WIDGET
    assert "QDesktopServices.openUrl" in WIDGET
    assert "QUrl.fromLocalFile" in WIDGET


def test_export_shows_success_dialog():
    export_start = WIDGET.index("def _export_session_pdf")
    export_end = WIDGET.index("def _show_export_success_dialog", export_start)
    export_block = WIDGET[export_start:export_end]
    assert "self._show_export_success_dialog(output_path)" in export_block
