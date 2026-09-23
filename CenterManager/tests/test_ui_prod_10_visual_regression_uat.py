# -*- coding: utf-8 -*-
"""UI-PROD-10 visual regression and physical UAT contracts."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget

from centermanager.ui.application_shell import ApplicationTopBar
from centermanager.ui.design_system.form_detail import DetailSection, EditStateBanner, FormField, FormSection
from centermanager.ui.design_system.foundation import Badge, Button, EmptyState, Input, Select
from centermanager.ui.design_system.tokens import COLORS, COMPONENT_METRICS, SPACING
from centermanager.ui.workspace_header import WorkspaceHeader

ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "tests" / "visual_baselines" / "ui_prod_10_gallery.json"
ARTIFACT_DIR = ROOT / "visual-regression-artifacts" / "ui_prod_10"
UAT_DOC = ROOT / "docs" / "ui_baseline" / "UI_PROD_10_UAT_CHECKLIST.md"
UAT_TEMPLATE = ROOT / "docs" / "ui_baseline" / "UI_PROD_10_UAT_EVIDENCE_TEMPLATE.json"
WORKFLOW = ROOT.parent / ".github" / "workflows" / "pytest-suite.yml"
VERIFY_SCRIPT = ROOT / "scripts" / "verify_ui_uat.py"


def _load_verifier():
    spec = importlib.util.spec_from_file_location("verify_ui_uat", VERIFY_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    yield instance


class VisualRegressionGallery(QWidget):
    """Deterministic production-component gallery used only by the visual gate."""

    def __init__(self, state: str) -> None:
        super().__init__()
        self.visual_state = state
        self.setObjectName("UIProd10VisualGallery")
        self.setFixedSize(1280, 720)
        self.setStyleSheet(
            f"QWidget#UIProd10VisualGallery {{ background: {COLORS['surface_app']}; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.top_bar = ApplicationTopBar(
            user_name="Nguyen Hoai An",
            role_name="Administrator",
            runtime_version="v1.0.0-rc1",
            sync_status="idle",
            parent=self,
        )
        root.addWidget(self.top_bar)

        self.header = WorkspaceHeader("Student Workspace", "Students", self)
        root.addWidget(self.header)

        content = QWidget(self)
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(SPACING["xl"], SPACING["lg"], SPACING["xl"], SPACING["xl"])
        content_layout.setSpacing(SPACING["lg"])

        form = FormSection("Student editor", "Production form, validation and edit-state hierarchy.", parent=content)
        name_input = Input("Student name", clearable=True)
        name_input.setText("Nguyen Minh Anh")
        form.add_field(FormField("Student name", name_input, required=True, helper_text="Use the student's full name."))
        form.add_field(FormField("Status", Select(["Active", "Trial", "Archived"], placeholder="Choose status")))
        self.edit_banner = EditStateBanner("readonly", parent=form)
        form.fields_layout.addWidget(self.edit_banner)

        actions = QWidget(form)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(SPACING["sm"])
        actions_layout.addWidget(Button("Save", variant="primary"))
        actions_layout.addWidget(Button("Secondary", variant="secondary"))
        actions_layout.addWidget(Button("Archive", variant="danger"))
        actions_layout.addStretch()
        form.fields_layout.addWidget(actions)
        content_layout.addWidget(form, 1)

        right = QWidget(content)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(SPACING["lg"])
        detail = DetailSection("Student summary", "Read-only detail hierarchy.", parent=right)
        detail.add_row("Student code", "STU-001")
        detail.add_row("Guardian", "Nguyen Van A · 0900 000 000")
        detail.add_widget(Badge("ACTIVE", tone="success"))
        right_layout.addWidget(detail)
        right_layout.addWidget(
            EmptyState(
                icon="i",
                title="No matching records",
                description="Clear the search or change filters to see students.",
                action_text="Clear filters",
                parent=right,
            ),
            1,
        )
        content_layout.addWidget(right, 1)
        root.addWidget(content, 1)

        self._apply_state(state)

    def _apply_state(self, state: str) -> None:
        if state == "read":
            self.top_bar.set_mode("READ", "neutral")
            self.edit_banner.set_state("readonly")
            return
        if state == "write_saved":
            self.top_bar.set_mode("WRITE", "success")
            self.top_bar.set_editor_state("You are editing", "success")
            self.top_bar.set_transaction_text("Editing")
            self.top_bar.start_edit_button.setVisible(False)
            self.top_bar.finish_edit_button.setVisible(True)
            self.edit_banner.set_state("editing")
            self.top_bar.notify_success("Student saved ✓")
            return
        if state == "error":
            self.top_bar.set_mode("READ", "neutral")
            self.edit_banner.set_state("readonly")
            self.top_bar.notify_error("Unable to refresh student data")
            return
        raise ValueError(f"Unknown visual state: {state}")


def _semantic_snapshot(gallery: VisualRegressionGallery) -> dict[str, object]:
    return {
        "mode_text": gallery.top_bar.mode_badge.text(),
        "edit_state": gallery.edit_banner.state,
        "feedback_visible": gallery.top_bar.feedback_host.isVisible(),
        "start_edit_visible": gallery.top_bar.start_edit_button.isVisible(),
        "finish_edit_visible": gallery.top_bar.finish_edit_button.isVisible(),
    }


def _sampled_color_count(image: QImage) -> int:
    step_x = max(1, image.width() // 80)
    step_y = max(1, image.height() // 45)
    colors = {
        image.pixelColor(x, y).rgba()
        for x in range(0, image.width(), step_x)
        for y in range(0, image.height(), step_y)
    }
    return len(colors)


def _emit_visual_artifact(gallery: VisualRegressionGallery, state: str) -> tuple[QImage, int, Path]:
    """Capture before assertions so failed visual gates still leave review evidence."""
    image = gallery.grab().toImage()
    sampled_colors = _sampled_color_count(image) if not image.isNull() else 0
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    png_path = ARTIFACT_DIR / f"{state}.png"
    if not image.isNull():
        image.save(str(png_path), "PNG")
    manifest = {
        "state": state,
        "semantic": _semantic_snapshot(gallery),
        "image": {"width": image.width(), "height": image.height(), "sampled_colors": sampled_colors},
        "png": png_path.name,
    }
    (ARTIFACT_DIR / f"{state}.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return image, sampled_colors, png_path


def test_visual_baseline_is_token_aligned():
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    assert baseline["geometry"]["top_bar_min_height"] == COMPONENT_METRICS["app_top_bar_height"]
    assert baseline["geometry"]["page_header_min_height"] == COMPONENT_METRICS["page_header_height"]
    assert baseline["viewport"] == {"width": 1280, "height": 720}


@pytest.mark.parametrize("state", ["read", "write_saved", "error"])
def test_visual_gallery_matches_baseline_and_emits_png(app, state):
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    gallery = VisualRegressionGallery(state)
    gallery.show()
    app.processEvents()

    image, sampled_colors, png_path = _emit_visual_artifact(gallery, state)

    assert gallery.size().width() == baseline["viewport"]["width"]
    assert gallery.size().height() == baseline["viewport"]["height"]
    assert gallery.top_bar.minimumHeight() == baseline["geometry"]["top_bar_min_height"]
    assert gallery.header.minimumHeight() == baseline["geometry"]["page_header_min_height"]
    assert gallery.header.page_title_label.text() == "Students"
    assert _semantic_snapshot(gallery) == baseline["states"][state]

    assert not image.isNull()
    assert image.width() == baseline["viewport"]["width"]
    assert image.height() == baseline["viewport"]["height"]
    assert sampled_colors >= baseline["image_quality"]["min_sampled_colors"]
    assert png_path.is_file()
    assert png_path.stat().st_size >= baseline["image_quality"]["min_png_bytes"]
    gallery.close()


def _write_png(path: Path, index: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = QImage(400, 240, QImage.Format.Format_RGB32)
    image.fill(QColor(240 - index, 245 - index, 250 - index))
    assert image.save(str(path), "PNG")


def _passing_uat_evidence(tmp_path: Path, verifier) -> tuple[dict, Path]:
    evidence_file = tmp_path / "evidence.json"
    scenarios = []
    for index, scenario_id in enumerate(verifier.REQUIRED_SCENARIOS):
        requirement = verifier.SCENARIO_REQUIREMENTS[scenario_id]
        width, height = requirement.get("viewport", (1366, 768))
        scale = requirement.get("scale_percent", requirement.get("min_scale_percent", 100))
        screenshot = Path("screenshots") / f"{index + 1:02d}-{scenario_id}.png"
        _write_png(tmp_path / screenshot, index)
        scenarios.append(
            {
                "id": scenario_id,
                "status": "PASS",
                "viewport": {"width": width, "height": height},
                "scale_percent": scale,
                "screenshot": screenshot.as_posix(),
                "notes": "verified",
            }
        )
    data = {
        "schema": verifier.SCHEMA,
        "task": verifier.TASK,
        "source_commit": "a" * 40,
        "build_version": "1.0.0-rc1",
        "scenarios": scenarios,
    }
    evidence_file.write_text(json.dumps(data), encoding="utf-8")
    return data, evidence_file


def test_uat_verifier_accepts_complete_visual_evidence(tmp_path):
    verifier = _load_verifier()
    data, evidence_file = _passing_uat_evidence(tmp_path, verifier)
    assert verifier.verify_evidence(data, evidence_file) == []


def test_uat_verifier_fails_closed_for_missing_status_and_unsafe_path(tmp_path):
    verifier = _load_verifier()
    data, evidence_file = _passing_uat_evidence(tmp_path, verifier)
    data["scenarios"][0]["status"] = "PENDING"
    data["scenarios"][1]["screenshot"] = "../outside.png"
    errors = verifier.verify_evidence(data, evidence_file)
    assert any("must be PASS" in error for error in errors)
    assert any("must be relative" in error or "escapes" in error for error in errors)


def test_checked_in_uat_template_is_intentionally_not_a_pass_record():
    verifier = _load_verifier()
    data = json.loads(UAT_TEMPLATE.read_text(encoding="utf-8"))
    errors = verifier.verify_evidence(data, UAT_TEMPLATE)
    assert errors
    assert any("source_commit" in error for error in errors)
    assert any("must be PASS" in error for error in errors)


def test_uat_docs_cover_every_required_scenario_and_ci_uploads_visual_artifacts():
    verifier = _load_verifier()
    doc = UAT_DOC.read_text(encoding="utf-8")
    for scenario_id in verifier.REQUIRED_SCENARIOS:
        assert scenario_id in doc
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "ui-prod-10-visual-evidence-${{ github.run_id }}" in workflow
    assert "CenterManager/visual-regression-artifacts/ui_prod_10" in workflow
