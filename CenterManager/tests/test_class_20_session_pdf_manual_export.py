from pathlib import Path

SERVICE = Path("src/centermanager/services/session_report_service.py").read_text(encoding="utf-8")
GENERATOR = Path("src/centermanager/export/pdf/session_report_generator.py").read_text(encoding="utf-8")
WIDGET = Path("src/centermanager/ui/class_workspace/class_schedule_widget.py").read_text(encoding="utf-8")


def test_latest_only_output_path():
    assert 'get_paths().session_report_dir' in SERVICE
    assert 'Class_{class_obj.id}_{class_obj.name}' in SERVICE
    assert 'Lesson_{session.session_number}_{lesson_title}' in SERVICE
    assert '/ "latest.pdf"' in SERVICE


def test_generation_uses_temp_then_atomic_replace():
    assert 'with_suffix(".tmp.pdf")' in SERVICE
    assert "os.replace(temp_path, output_path)" in SERVICE


def test_pdf_contains_parent_group_session_sections():
    for text in ("BÁO CÁO BUỔI HỌC", "NỘI DUNG BUỔI HỌC", "BÀI TẬP VỀ NHÀ", "CHUYÊN CẦN"):
        assert text in GENERATOR


def test_pdf_includes_selected_session_highlights():
    assert "ĐIỂM NỔI BẬT HỌC SINH" in GENERATOR
    assert 'data.get("highlights")' in GENERATOR


def test_schedule_has_manual_export_action():
    assert 'QPushButton("Export PDF")' in WIDGET
    assert "def _export_session_pdf" in WIDGET
    assert "generate_session_report(session_id)" in WIDGET


def test_export_does_not_require_write_mode():
    export_start = WIDGET.index("def _export_session_pdf")
    export_end = WIDGET.index("def _open_session_detail", export_start)
    export_block = WIDGET[export_start:export_end]
    assert "ensure_write" not in export_block
