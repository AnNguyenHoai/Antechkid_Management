# -*- coding: utf-8 -*-
"""Post-UI-PROD audit hardening regression contracts."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFY_SCRIPT = ROOT / "scripts" / "verify_ui_uat.py"
UI_PROD_08_DOC = ROOT / "docs" / "ui_baseline" / "UI_PROD_08_STUDENT_WORKSPACE_MIGRATION.md"
UI_PROD_10_DOC = ROOT / "docs" / "ui_baseline" / "UI_PROD_10_VISUAL_REGRESSION_UAT.md"
UI_PROD_10_CHECKLIST = ROOT / "docs" / "ui_baseline" / "UI_PROD_10_UAT_CHECKLIST.md"


def _load_verifier():
    spec = importlib.util.spec_from_file_location("verify_ui_uat_audit", VERIFY_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_uat_release_binding_accepts_exact_provenance():
    verifier = _load_verifier()
    data = {
        "source_commit": "a" * 40,
        "build_version": "1.0.0-rc1",
    }

    assert verifier.verify_release_binding(
        data,
        expected_source_commit="a" * 40,
        expected_build_version="1.0.0-rc1",
    ) == []


def test_uat_release_binding_rejects_wrong_commit_and_version():
    verifier = _load_verifier()
    data = {
        "source_commit": "a" * 40,
        "build_version": "1.0.0-rc1",
    }

    errors = verifier.verify_release_binding(
        data,
        expected_source_commit="b" * 40,
        expected_build_version="1.0.0-rc2",
    )

    assert "source_commit does not match the expected release commit" in errors
    assert "build_version does not match the expected release version" in errors


def test_uat_cli_requires_expected_release_provenance():
    source = VERIFY_SCRIPT.read_text(encoding="utf-8")
    assert '"--expected-source-commit"' in source
    assert '"--expected-build-version"' in source
    assert source.count("required=True") >= 2
    assert "verify_release_binding(" in source


def test_uat_docs_use_provenance_bound_verifier_command():
    for path in (UI_PROD_10_DOC, UI_PROD_10_CHECKLIST):
        source = path.read_text(encoding="utf-8")
        assert "--expected-source-commit" in source
        assert "--expected-build-version" in source


def test_student_migration_scope_supersedes_older_broader_roadmap_copy():
    source = UI_PROD_08_DOC.read_text(encoding="utf-8")
    assert "Scope: Student Workspace only" in source
    assert "supersedes" in source.lower()
    for workspace in ("Teacher", "Class", "Finance", "Employee", "Admin"):
        assert workspace in source
