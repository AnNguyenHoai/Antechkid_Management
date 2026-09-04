# -*- coding: utf-8 -*-
"""Early UI diagnostics for QMessageBox-based permission popups."""
from __future__ import annotations

import datetime as _dt
import os as _os
import traceback as _traceback


def _diagnostic_path() -> str:
    root = _os.path.dirname(_os.path.abspath(__file__))
    log_dir = _os.path.join(root, "runtime", "Logs")
    _os.makedirs(log_dir, exist_ok=True)
    return _os.path.join(log_dir, "ui_popup_diagnostics.log")


def _write_diagnostic(kind: str, title: object, text: object) -> None:
    try:
        timestamp = _dt.datetime.now().astimezone().isoformat(timespec="seconds")
        stack = "".join(_traceback.format_stack(limit=30))
        with open(_diagnostic_path(), "a", encoding="utf-8") as fh:
            fh.write("\n=== UI POPUP DIAGNOSTIC ===\n")
            fh.write(f"timestamp={timestamp}\n")
            fh.write(f"kind={kind}\n")
            fh.write(f"title={title!s}\n")
            fh.write(f"text={text!s}\n")
            fh.write("caller_stack:\n")
            fh.write(stack)
            fh.write("=== END UI POPUP DIAGNOSTIC ===\n")
    except Exception:
        pass


def _install() -> None:
    try:
        from PySide6.QtWidgets import QMessageBox
    except Exception:
        try:
            from PyQt6.QtWidgets import QMessageBox
        except Exception:
            return

    for method_name in ("warning", "critical", "information"):
        original = getattr(QMessageBox, method_name, None)
        if original is None or getattr(original, "_centermanager_diagnostic", False):
            continue

        def wrapper(*args, __original=original, __kind=method_name, **kwargs):
            title = args[1] if len(args) > 1 else kwargs.get("title", "")
            text = args[2] if len(args) > 2 else kwargs.get("text", "")
            _write_diagnostic(__kind, title, text)
            return __original(*args, **kwargs)

        wrapper._centermanager_diagnostic = True
        setattr(QMessageBox, method_name, staticmethod(wrapper))


_install()
