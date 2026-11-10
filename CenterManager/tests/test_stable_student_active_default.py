"""Operational student tables default to ACTIVE; historical records are still selectable."""
from pathlib import Path


def test_student_overview_defaults_active_without_changing_query_scope():
    source = (Path(__file__).resolve().parents[1] /
              "src/centermanager/ui/student_workspace/student_overview_page.py").read_text(encoding="utf-8")
    assert 'self.status.addItem("Tất cả trạng thái", None)' in source
    assert 'self.status.addItem("Đang hoạt động", "ACTIVE")' in source
    assert 'self.status.setCurrentIndex(1)' in source
    assert 'self.status.addItem("Archived", "ARCHIVED")' in source
    assert 'self._service.list_rows(year=self.year.value(), month=self.month.value())' in source


def test_student_list_already_defaults_active():
    source = (Path(__file__).resolve().parents[1] /
              "src/centermanager/ui/student_workspace/student_list_page.py").read_text(encoding="utf-8")
    assert 'self.search_bar.set_filter_value("status", "Active")' in source
