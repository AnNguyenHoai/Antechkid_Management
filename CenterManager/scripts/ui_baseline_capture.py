#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI-PROD-00 visual baseline recorder for a real CenterManager session.

Run this instead of ``run.py`` on a reference workstation. It starts the normal
application and injects a process-local Ctrl+Shift+B shortcut only into that
run. The production startup path and UI behavior are otherwise unchanged.
"""
from __future__ import annotations

import json
import os
import platform
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

BASELINE_REVISION = "df39c7adcd3c896674163fb0ce95dc55abd135f2"
ID_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


PROJECT_ROOT = _project_root()
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from PySide6.QtCore import qVersion
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QInputDialog, QMainWindow, QMessageBox, QStackedWidget, QWidget


def _snake_case(name: str) -> str:
    first = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", first).lower()


def _safe_id(value: str) -> str:
    value = ID_RE.sub("-", value.strip()).strip(".-_").lower()
    return value or "screen"


def _default_output_dir() -> Path:
    override = os.environ.get("CENTERMANAGER_UI_BASELINE_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return PROJECT_ROOT / "artifacts" / "ui-baseline" / BASELINE_REVISION[:12]


def _deepest_active_surface(window: QMainWindow) -> QWidget:
    """Best-effort active page resolution without depending on workspace classes."""
    surface: QWidget = window.centralWidget()
    central_stack = getattr(window, "central_stack", None)
    if isinstance(central_stack, QStackedWidget) and central_stack.currentWidget():
        surface = central_stack.currentWidget()
    content_stack = getattr(surface, "content_stack", None)
    if isinstance(content_stack, QStackedWidget) and content_stack.currentWidget():
        surface = content_stack.currentWidget()
    return surface


def _suggested_id(window: QMainWindow) -> str:
    surface = _deepest_active_surface(window)
    class_name = surface.__class__.__name__
    module = surface.__class__.__module__
    parts = module.split(".")
    area = "app"
    if "ui" in parts:
        index = parts.index("ui")
        if index + 1 < len(parts) - 1:
            area = parts[index + 1]
    return _safe_id(f"{area}.{_snake_case(class_name)}")


class VisualBaselineRecorder:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir.resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.output_dir / "manifest.json"

    def _widget_metadata(self, widget: QWidget) -> dict:
        screen = widget.screen()
        return {
            "class": widget.__class__.__name__,
            "module": widget.__class__.__module__,
            "width": widget.width(),
            "height": widget.height(),
            "device_pixel_ratio": float(widget.devicePixelRatioF()),
            "logical_dpi": float(screen.logicalDotsPerInch()) if screen else None,
        }

    @staticmethod
    def _save_grab(widget: QWidget, target: Path) -> None:
        pixmap = widget.grab()
        if pixmap.isNull() or not pixmap.save(str(target), "PNG"):
            raise RuntimeError(f"Could not save screenshot: {target}")

    def _load_manifest(self) -> dict:
        if not self.manifest_path.exists():
            return {"schema_version": 1, "baseline_revision": BASELINE_REVISION, "captures": []}
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def capture(self, window: QMainWindow, baseline_id: str) -> dict:
        baseline_id = _safe_id(baseline_id)
        surface = _deepest_active_surface(window)
        window_file = f"{baseline_id}__window.png"
        surface_file = f"{baseline_id}__surface.png"
        self._save_grab(window, self.output_dir / window_file)
        self._save_grab(surface, self.output_dir / surface_file)
        record = {
            "id": baseline_id,
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "qt": qVersion(),
            "window_file": window_file,
            "surface_file": surface_file,
            "window": self._widget_metadata(window),
            "surface": self._widget_metadata(surface),
        }
        manifest = self._load_manifest()
        manifest["baseline_revision"] = BASELINE_REVISION
        manifest["captures"] = [item for item in manifest.get("captures", []) if item.get("id") != baseline_id]
        manifest["captures"].append(record)
        manifest["captures"].sort(key=lambda item: item["id"])
        self.manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return record


def install_capture_shortcut(window: QMainWindow, output_dir: Path) -> None:
    recorder = VisualBaselineRecorder(output_dir)
    shortcut = QShortcut(QKeySequence("Ctrl+Shift+B"), window)

    def on_capture() -> None:
        suggestion = _suggested_id(window)
        baseline_id, accepted = QInputDialog.getText(window, "UI visual baseline", "Baseline ID:", text=suggestion)
        if not accepted or not baseline_id.strip():
            return
        try:
            record = recorder.capture(window, baseline_id)
        except Exception as exc:
            QMessageBox.critical(window, "Baseline capture failed", str(exc))
            return
        QMessageBox.information(window, "Baseline captured", f"Saved {record['id']}\n\n{recorder.output_dir}")

    shortcut.activated.connect(on_capture)
    window._ui_baseline_recorder = recorder
    window._ui_baseline_shortcut = shortcut


def main() -> int:
    output_dir = _default_output_dir()
    from centermanager.ui.main_window import MainWindow
    original_show = MainWindow.show

    def show_with_baseline(self: QMainWindow) -> None:
        install_capture_shortcut(self, output_dir)
        original_show(self)

    MainWindow.show = show_with_baseline
    print(f"UI baseline mode: {BASELINE_REVISION}")
    print(f"Capture directory: {output_dir}")
    print("After login/navigation press Ctrl+Shift+B to record the current screen.")
    from centermanager.app import main as app_main
    result = app_main()
    return int(result) if isinstance(result, int) else 0


if __name__ == "__main__":
    raise SystemExit(main())
