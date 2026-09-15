from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = ROOT / "src" / "centermanager" / "ui" / "employee_workspace"


def _source(name):
    return (WORKSPACE / name).read_text(encoding="utf-8")


def test_schedule_operations_use_runtime_error_boundary():
    source = _source("employee_schedule_widget.py")
    assert "execute_ui_operation" in source
    assert "logger = logging.getLogger(__name__)" in source
    assert "except Exception as exc:" not in source


def test_working_time_operations_use_runtime_error_boundary():
    source = _source("employee_working_time_widget.py")
    assert "execute_ui_operation" in source
    assert "logger = logging.getLogger(__name__)" in source
    assert "except Exception as exc:" not in source


def test_checkout_blocks_ambiguous_multiple_open_entries():
    source = _source("employee_working_time_widget.py")
    assert "len(open_rows) > 1" in source
    assert "check-out was blocked to protect data integrity" in source
