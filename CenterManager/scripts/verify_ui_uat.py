#!/usr/bin/env python3
"""Fail-closed verifier for UI-PROD-10 physical UI UAT evidence."""
from __future__ import annotations

import argparse
import json
import re
import struct
from pathlib import Path
from typing import Any

SCHEMA = "UI-PROD-10/v1"
TASK = "UI-PROD-10"

SCENARIO_REQUIREMENTS = {
    "shell-1366x768": {"viewport": (1366, 768), "scale_percent": 100},
    "shell-1920x1080": {"viewport": (1920, 1080), "scale_percent": 100},
    "shell-scale-125": {"min_scale_percent": 125},
    "student-list-read": {},
    "student-list-write": {},
    "student-form-validation-save": {},
    "student-detail-tabs": {},
    "enrollment-confirmation-feedback": {},
    "loading-empty-error-permission": {},
    "window-restore-overflow-focus": {},
}
REQUIRED_SCENARIOS = tuple(SCENARIO_REQUIREMENTS)

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _png_dimensions(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if len(header) < 24 or header[:8] != _PNG_SIGNATURE or header[12:16] != b"IHDR":
        raise ValueError("not a valid PNG header")
    return struct.unpack(">II", header[16:24])


def _resolve_screenshot(evidence_file: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("screenshot path must be relative and remain inside the evidence directory")
    root = evidence_file.parent.resolve()
    resolved = (root / candidate).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError("screenshot path escapes the evidence directory")
    return resolved


def verify_evidence(data: dict[str, Any], evidence_file: Path) -> list[str]:
    """Return validation errors. An empty list means PASS."""
    errors: list[str] = []

    if data.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    if data.get("task") != TASK:
        errors.append(f"task must be {TASK}")

    source_commit = str(data.get("source_commit", "")).strip().lower()
    if not _SHA40.fullmatch(source_commit):
        errors.append("source_commit must be a lowercase 40-character Git SHA")
    if not str(data.get("build_version", "")).strip():
        errors.append("build_version is required")

    scenarios = data.get("scenarios")
    if not isinstance(scenarios, list):
        return errors + ["scenarios must be a list"]

    by_id: dict[str, list[dict[str, Any]]] = {}
    for item in scenarios:
        if not isinstance(item, dict):
            errors.append("every scenario must be an object")
            continue
        scenario_id = str(item.get("id", "")).strip()
        by_id.setdefault(scenario_id, []).append(item)

    screenshot_paths: set[Path] = set()
    for scenario_id, requirement in SCENARIO_REQUIREMENTS.items():
        matches = by_id.get(scenario_id, [])
        if len(matches) != 1:
            errors.append(f"scenario {scenario_id!r} must appear exactly once")
            continue
        scenario = matches[0]
        if scenario.get("status") != "PASS":
            errors.append(f"scenario {scenario_id!r} must be PASS")

        viewport = scenario.get("viewport")
        if not isinstance(viewport, dict):
            errors.append(f"scenario {scenario_id!r} requires viewport evidence")
            viewport = {}
        width = viewport.get("width")
        height = viewport.get("height")
        if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
            errors.append(f"scenario {scenario_id!r} viewport must contain positive integer width/height")

        scale = scenario.get("scale_percent")
        if not isinstance(scale, int) or scale <= 0:
            errors.append(f"scenario {scenario_id!r} scale_percent must be a positive integer")

        expected_viewport = requirement.get("viewport")
        if expected_viewport and (width, height) != expected_viewport:
            errors.append(
                f"scenario {scenario_id!r} must run at {expected_viewport[0]}x{expected_viewport[1]}"
            )
        expected_scale = requirement.get("scale_percent")
        if expected_scale and scale != expected_scale:
            errors.append(f"scenario {scenario_id!r} must run at {expected_scale}% scale")
        minimum_scale = requirement.get("min_scale_percent")
        if minimum_scale and isinstance(scale, int) and scale < minimum_scale:
            errors.append(f"scenario {scenario_id!r} must run at >= {minimum_scale}% scale")

        raw_screenshot = str(scenario.get("screenshot", "")).strip()
        if not raw_screenshot:
            errors.append(f"scenario {scenario_id!r} requires a screenshot path")
            continue
        try:
            screenshot = _resolve_screenshot(evidence_file, raw_screenshot)
        except ValueError as exc:
            errors.append(f"scenario {scenario_id!r}: {exc}")
            continue
        if screenshot in screenshot_paths:
            errors.append(f"scenario {scenario_id!r} reuses another scenario screenshot")
        screenshot_paths.add(screenshot)
        if screenshot.suffix.lower() != ".png":
            errors.append(f"scenario {scenario_id!r} screenshot must be PNG")
            continue
        if not screenshot.is_file():
            errors.append(f"scenario {scenario_id!r} screenshot does not exist: {raw_screenshot}")
            continue
        try:
            image_width, image_height = _png_dimensions(screenshot)
        except (OSError, ValueError) as exc:
            errors.append(f"scenario {scenario_id!r} screenshot is invalid: {exc}")
            continue
        if image_width < 320 or image_height < 200:
            errors.append(f"scenario {scenario_id!r} screenshot is too small for visual review")

    extras = sorted(set(by_id) - set(REQUIRED_SCENARIOS) - {""})
    if extras:
        errors.append(f"unexpected scenario ids: {', '.join(extras)}")
    if "" in by_id:
        errors.append("scenario id must not be empty")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path, help="Path to completed UI-PROD-10 evidence JSON")
    args = parser.parse_args()

    try:
        data = json.loads(args.evidence.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"UI-PROD-10 UAT FAIL: cannot read evidence: {exc}")
        return 2

    errors = verify_evidence(data, args.evidence)
    if errors:
        print("UI-PROD-10 UAT FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("UI-PROD-10 UAT PASS")
    print(f"- source commit: {data['source_commit']}")
    print(f"- build version: {data['build_version']}")
    print(f"- scenarios: {len(REQUIRED_SCENARIOS)}/{len(REQUIRED_SCENARIOS)} PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
