"""Regression contract for EP-PROTOTYPE-01.

The prototype scope is intentionally documented as a product/UX contract. These
checks prevent accidental scope drift while follow-up implementation tasks are
built incrementally.
"""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCOPE_PATH = PROJECT_ROOT / "docs" / "PROTOTYPE_SCOPE.md"


EXPECTED_SECTIONS = {
    "## 1. Purpose",
    "## 2. Existing Product Contracts Used",
    "## 3. Prototype Goal",
    "## 4. Prototype Scope",
    "## 5. Golden Flow Acceptance Criteria",
    "## 6. Navigation Contract",
    "## 7. Prototype Non-Goals",
    "## 8. Implementation Rules for Follow-up Prototype Tasks",
    "## 9. Prototype Completion Gate",
    "## 10. Out-of-Scope Decisions Deferred Until UAT",
}


REQUIRED_WORKSPACE_MARKERS = {
    "### P0 — Application Entry",
    "### P1 — Student Workspace",
    "### P2 — Class Workspace",
    "### P3 — Teacher Workspace",
    "### P4 — Session",
    "### P5 — Attendance",
    "### P6 — Assessment",
    "### P7 — Student Timeline",
    "### P8 — Finance Basic",
    "### P9 — Dashboard Integration",
}


def _scope_text() -> str:
    assert SCOPE_PATH.is_file(), f"Prototype scope contract missing: {SCOPE_PATH}"
    return SCOPE_PATH.read_text(encoding="utf-8")


def test_ep_prototype_01_scope_contract_contains_required_sections():
    text = _scope_text()
    missing = sorted(section for section in EXPECTED_SECTIONS if section not in text)
    assert not missing, "Prototype scope contract is missing required sections:\n" + "\n".join(missing)


def test_ep_prototype_01_scope_contract_covers_all_prototype_slices():
    text = _scope_text()
    missing = sorted(marker for marker in REQUIRED_WORKSPACE_MARKERS if marker not in text)
    assert not missing, "Prototype scope contract is missing required slices:\n" + "\n".join(missing)


def test_ep_prototype_01_scope_contract_freezes_golden_flow():
    text = _scope_text()
    required_flow = [
        "Open Home",
        "Open Student Workspace",
        "Open Student",
        "View Class / Enrollment",
        "Open Class",
        "Open Session",
        "Mark Attendance",
        "Record Assessment",
        "Return to Student",
        "See Timeline update",
    ]
    missing = [step for step in required_flow if step not in text]
    assert not missing, "Golden Flow A is incomplete:\n" + "\n".join(missing)


def test_ep_prototype_01_scope_contract_freezes_finance_flow():
    text = _scope_text()
    required_flow = [
        "Open Finance",
        "View Income",
        "View Expense",
        "View Balance",
    ]
    missing = [step for step in required_flow if step not in text]
    assert not missing, "Golden Flow B is incomplete:\n" + "\n".join(missing)


def test_ep_prototype_01_does_not_require_new_architecture_layers():
    text = _scope_text()
    required_non_goals = [
        "New event-bus architecture.",
        "CQRS or new application layers.",
        "New repository abstractions.",
        "Broad architecture refactoring merely to satisfy this scope document.",
    ]
    missing = [item for item in required_non_goals if item not in text]
    assert not missing, "Prototype non-goals drifted; architecture scope must remain frozen:\n" + "\n".join(missing)
