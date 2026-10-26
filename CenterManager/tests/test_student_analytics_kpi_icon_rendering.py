# -*- coding: utf-8 -*-
"""Regression contract for Student Analytics KPI icon rendering."""
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
UI = ROOT / "src" / "centermanager" / "ui"


def _source(relative: str) -> str:
    return (UI / relative).read_text(encoding="utf-8")


def test_student_analytics_uses_semantic_vector_icons_for_kpis():
    source = _source("student_workspace/student_analytics_page.py")

    assert 'MetricCard(\n            "reports", "Average Score"' in source
    assert 'MetricCard(\n            "student", "Total Students"' in source
    assert 'MetricCard(\n            "trend", "Monthly Growth"' in source
    assert 'MetricCard("Score", "Average Score"' not in source
    assert 'MetricCard("Students", "Total Students"' not in source
    assert 'MetricCard("Growth", "Monthly Growth"' not in source


def test_trend_icon_is_available_in_deterministic_app_icon_set():
    source = _source("app_icon.py")
    assert '"trend":' in source
