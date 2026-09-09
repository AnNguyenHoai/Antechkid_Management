from pathlib import Path


def test_employee_workspace_capabilities_uses_valid_future_annotations_import():
    source = Path(
        "CenterManager/src/centermanager/ui/employee_workspace/employee_workspace_capabilities.py"
    ).read_text(encoding="utf-8")

    assert "from __future__ import annotations\n" in source
    assert "from __future__ import annotations__" not in source
