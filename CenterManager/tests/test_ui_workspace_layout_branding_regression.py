from pathlib import Path

from centermanager.core.application_identity import (
    APPLICATION_DISPLAY_NAME,
    APPLICATION_INTERNAL_NAME,
    APPLICATION_PRODUCT_NAME,
)
from centermanager.core.config import Config


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "centermanager"


def _source(relative: str) -> str:
    return (SRC / relative).read_text(encoding="utf-8")


def test_visible_app_identity_changes_without_renaming_internal_runtime_identity():
    assert APPLICATION_DISPLAY_NAME == "AnTechKids - Management App"
    assert APPLICATION_PRODUCT_NAME == "AnTechKids Management App"
    assert APPLICATION_INTERNAL_NAME == "CenterManager"


def test_runtime_config_keeps_centermanager_identity():
    config = Config({"application": {"name": APPLICATION_DISPLAY_NAME}})
    assert config.get("application.name") == "CenterManager"


def test_student_selection_controls_do_not_add_a_dynamic_vertical_row():
    source = _source("ui/student_workspace/student_list_page.py")
    assert 'toolbar.add_widget(self.bulk_bar, align="end")' in source
    assert "layout.addWidget(self.bulk_bar)" not in source


def test_teacher_selection_uses_page_aware_data_mapping_and_stable_toolbar():
    source = _source("ui/teacher_workspace/teacher_list_page.py")
    assert "top_row.addWidget(self.bulk_bar)" in source
    assert "layout.addWidget(self.bulk_bar)" not in source
    assert source.count("data_index_for_visible_row") >= 3


def test_shared_workspace_tables_stretch_columns_evenly():
    source = _source("ui/shared/__init__.py")
    assert "QHeaderView.ResizeMode.Stretch" in source
    assert "setStretchLastSection(False)" in source


def test_student_enrollment_uses_grid_layout_for_summary_and_actions():
    source = _source("ui/student_workspace/enrollment_widget.py")
    assert "self.overview_layout = QGridLayout" in source
    assert "actions_layout = QGridLayout" in source
    assert "index // 3, index % 3" in source


def test_student_finance_uses_grid_summary_and_even_table_columns():
    source = _source("ui/student_workspace/student_financial_widget.py")
    assert "summary_layout = QGridLayout" in source
    assert source.count("QHeaderView.ResizeMode.Stretch") >= 2


def test_application_shell_applies_new_title_and_avatar():
    source = _source("ui/application_shell.py")
    assert "setWindowTitle(APPLICATION_DISPLAY_NAME)" in source
    assert "setWindowIcon(build_application_icon())" in source
    assert "QLabel(APPLICATION_PRODUCT_NAME)" in source
