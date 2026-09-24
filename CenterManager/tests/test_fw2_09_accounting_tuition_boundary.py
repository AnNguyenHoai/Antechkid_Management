from __future__ import annotations

from pathlib import Path


ROOT = Path("src/centermanager")

ACADEMIC_CORE = (
    ROOT / "models/class_.py",
    ROOT / "models/enrollment.py",
    ROOT / "models/session.py",
    ROOT / "services/class_service.py",
    ROOT / "services/enrollment_service.py",
    ROOT / "services/session_service.py",
)

FINANCE_PERIOD_DEPENDENCY_MARKERS = (
    "models.finance_period",
    "services.finance_period_service",
    "FinancePeriod",
    "FinancePeriodService",
)


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_academic_core_does_not_depend_on_accounting_finance_period():
    """Academic obligation must not acquire a FinancePeriod dependency."""
    for path in ACADEMIC_CORE:
        source = _source(path)
        for marker in FINANCE_PERIOD_DEPENDENCY_MARKERS:
            assert marker not in source, f"{path} depends on accounting period via {marker}"


def test_new_tuition_modules_do_not_import_accounting_period_contract():
    """Future tuition modules inherit the same boundary automatically."""
    candidate_dirs = (ROOT / "models", ROOT / "services")
    tuition_files = [
        path
        for directory in candidate_dirs
        for path in directory.glob("*tuition*.py")
    ]
    for path in tuition_files:
        source = _source(path)
        for marker in FINANCE_PERIOD_DEPENDENCY_MARKERS:
            assert marker not in source, f"{path} depends on accounting period via {marker}"


def test_outstanding_period_obligation_is_documented_as_transitional_exception():
    source = _source(ROOT / "services/outstanding_service.py")
    boundary = Path(
        "docs/finance/FINANCE_WALLET_V2_TUITION_BOUNDARY.md"
    ).read_text(encoding="utf-8")

    # The current read model still contains the pre-TUITION-08 period formula.
    # It is intentionally tolerated only while the approved amendment names it
    # as a transitional compatibility exception and points to the replacement.
    assert "FinancePeriod" in source
    assert "OutstandingService" in boundary
    assert "transitional" in boundary.lower()
    assert "TUITION-08" in boundary
    assert "#350" in boundary


def test_boundary_amendment_supersedes_per_period_tuition_semantics():
    boundary = Path(
        "docs/finance/FINANCE_WALLET_V2_TUITION_BOUNDARY.md"
    ).read_text(encoding="utf-8")

    assert "FinancePeriod == accounting / settlement boundary" in boundary
    assert "FinancePeriod != course / tuition obligation boundary" in boundary
    assert "Class.fee per FinancePeriod" in boundary
    assert "supersedes" in boundary.lower()
