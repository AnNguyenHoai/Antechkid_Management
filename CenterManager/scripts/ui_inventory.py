#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI-PROD-00: deterministic source inventory for CenterManager UI.

This tool deliberately uses only the Python standard library.  It scans the
PySide6 UI source tree without importing application modules, which keeps the
inventory safe to run on developer/CI machines without a database, runtime
configuration, or display server.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

BASELINE_REVISION = "df39c7adcd3c896674163fb0ce95dc55abd135f2"
SCHEMA_VERSION = 1
HEX_COLOR_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")

SCREEN_SUFFIXES = ("Page", "Window", "Wizard")
DIALOG_SUFFIXES = ("Dialog",)
SHELL_SUFFIXES = ("Shell",)
COMPONENT_SUFFIXES = (
    "Widget", "Card", "Header", "Navigation", "Toolbar", "Table", "Button",
    "Badge", "Avatar", "Item", "Grid", "Bar",
)
COMMON_QT_COMPONENT_BASES = {
    "QWidget", "QFrame", "QLabel", "QPushButton", "QLineEdit", "QComboBox",
    "QTableWidget", "QTabWidget", "QScrollArea", "QGroupBox", "QDialogButtonBox",
}


@dataclass(frozen=True)
class ClassInventory:
    area: str
    module: str
    path: str
    name: str
    line: int
    bases: tuple[str, ...]
    category: str
    baseline_id: str | None


@dataclass(frozen=True)
class FileInventory:
    area: str
    module: str
    path: str
    class_count: int
    stylesheet_calls: int
    raw_hex_colors: tuple[str, ...]
    imports_legacy_styles: bool
    imports_design_tokens: bool
    parse_error: str | None = None


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_ui_root() -> Path:
    return _project_root() / "src" / "centermanager" / "ui"


def _module_name(ui_root: Path, source: Path) -> str:
    rel = source.relative_to(ui_root).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(["centermanager", "ui", *parts])


def _area(ui_root: Path, source: Path) -> str:
    rel = source.relative_to(ui_root)
    return rel.parts[0] if len(rel.parts) > 1 else "app"


def _expr_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _expr_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    if isinstance(node, ast.Subscript):
        return _expr_name(node.value)
    return ast.unparse(node) if hasattr(ast, "unparse") else node.__class__.__name__


def _snake_case(name: str) -> str:
    first = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", first).lower()


def _classify(name: str, bases: Sequence[str]) -> str:
    base_names = {item.rsplit(".", 1)[-1] for item in bases}
    if name.endswith(SHELL_SUFFIXES):
        return "shell"
    if name.endswith(DIALOG_SUFFIXES) or "QDialog" in base_names:
        return "dialog"
    if name.endswith(SCREEN_SUFFIXES) or "QMainWindow" in base_names:
        return "screen"
    if name.endswith(COMPONENT_SUFFIXES) or base_names.intersection(COMMON_QT_COMPONENT_BASES):
        return "component"
    return "helper"


def _baseline_id(area: str, name: str, category: str) -> str | None:
    if category not in {"screen", "shell", "dialog"}:
        return None
    return f"{area}.{_snake_case(name)}"


def _imports(tree: ast.AST) -> set[str]:
    values: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            values.add(node.module)
    return values


def _stylesheet_calls(tree: ast.AST) -> int:
    return sum(
        1 for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "setStyleSheet"
    )


def _raw_hex_colors(source_text: str) -> tuple[str, ...]:
    return tuple(sorted(set(match.lower() for match in HEX_COLOR_RE.findall(source_text))))


def scan_ui(ui_root: Path) -> dict:
    """Return a JSON-serializable deterministic inventory for ``ui_root``."""
    ui_root = ui_root.resolve()
    classes: list[ClassInventory] = []
    files: list[FileInventory] = []

    for source in sorted(ui_root.rglob("*.py")):
        rel_path = source.relative_to(ui_root).as_posix()
        module = _module_name(ui_root, source)
        area = _area(ui_root, source)
        text = source.read_text(encoding="utf-8")

        try:
            tree = ast.parse(text, filename=str(source))
        except SyntaxError as exc:
            files.append(FileInventory(
                area=area, module=module, path=rel_path, class_count=0,
                stylesheet_calls=0, raw_hex_colors=_raw_hex_colors(text),
                imports_legacy_styles=False, imports_design_tokens=False,
                parse_error=f"{exc.msg} (line {exc.lineno})",
            ))
            continue

        module_classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
        imported = _imports(tree)

        for node in module_classes:
            bases = tuple(_expr_name(base) for base in node.bases)
            category = _classify(node.name, bases)
            classes.append(ClassInventory(
                area=area, module=module, path=rel_path, name=node.name,
                line=node.lineno, bases=bases, category=category,
                baseline_id=_baseline_id(area, node.name, category),
            ))

        files.append(FileInventory(
            area=area, module=module, path=rel_path, class_count=len(module_classes),
            stylesheet_calls=_stylesheet_calls(tree), raw_hex_colors=_raw_hex_colors(text),
            imports_legacy_styles="centermanager.ui.styles" in imported,
            imports_design_tokens="centermanager.ui.design_system.tokens" in imported,
        ))

    classes.sort(key=lambda x: (x.area, x.path, x.line, x.name))
    files.sort(key=lambda x: (x.area, x.path))
    category_counts = Counter(item.category for item in classes)
    area_counts = Counter(item.area for item in classes)

    return {
        "schema_version": SCHEMA_VERSION,
        "baseline_revision": BASELINE_REVISION,
        "ui_root": ui_root.as_posix(),
        "summary": {
            "files": len(files), "classes": len(classes),
            "categories": dict(sorted(category_counts.items())),
            "areas": dict(sorted(area_counts.items())),
        },
        "visual_debt": {
            "stylesheet_calls": sum(item.stylesheet_calls for item in files),
            "files_with_raw_hex_colors": sum(bool(item.raw_hex_colors) for item in files),
            "files_importing_legacy_styles": sum(item.imports_legacy_styles for item in files),
            "files_importing_design_tokens": sum(item.imports_design_tokens for item in files),
        },
        "classes": [asdict(item) for item in classes],
        "files": [asdict(item) for item in files],
    }


def _md_escape(value: object) -> str:
    return str(value).replace("|", r"\|").replace("\n", " ")


def _markdown_table(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_md_escape(value) for value in row) + " |")
    return lines


def render_markdown(inventory: dict) -> str:
    summary = inventory["summary"]
    debt = inventory["visual_debt"]
    classes = inventory["classes"]
    files = inventory["files"]
    lines = [
        "# UI-PROD-00 — UI Inventory", "",
        f"- Baseline revision: `{inventory['baseline_revision']}`",
        f"- UI Python files: **{summary['files']}**",
        f"- Top-level UI classes: **{summary['classes']}**",
        "- Generated by `scripts/ui_inventory.py`; do not maintain this list by hand.",
        "", "## Classification summary", "",
    ]
    lines += _markdown_table(["Category", "Count"], summary["categories"].items())
    lines += ["", "## Areas", ""]
    lines += _markdown_table(["Area", "Top-level classes"], summary["areas"].items())

    surfaces = [item for item in classes if item["category"] in {"screen", "shell", "dialog"}]
    lines += ["", "## Screens, shells and dialogs", "",
              "The baseline ID is the stable key used when recording screenshots. State-specific captures may append a suffix such as `.empty`, `.read`, or `.editing`.", ""]
    lines += _markdown_table(
        ["Baseline ID", "Category", "Class", "Source", "Line", "Bases"],
        ((item["baseline_id"] or "—", item["category"], item["name"], item["path"], item["line"], ", ".join(item["bases"]) or "—") for item in surfaces),
    )

    components = [item for item in classes if item["category"] == "component"]
    lines += ["", "## Reusable / embeddable components", ""]
    lines += _markdown_table(
        ["Area", "Class", "Source", "Line", "Bases"],
        ((item["area"], item["name"], item["path"], item["line"], ", ".join(item["bases"]) or "—") for item in components),
    )

    helpers = [item for item in classes if item["category"] == "helper"]
    lines += ["", "## UI helpers / non-widget classes", ""]
    lines += _markdown_table(
        ["Area", "Class", "Source", "Line", "Bases"],
        ((item["area"], item["name"], item["path"], item["line"], ", ".join(item["bases"]) or "—") for item in helpers),
    )

    lines += ["", "## Visual-debt baseline", "",
              f"- `setStyleSheet(...)` calls: **{debt['stylesheet_calls']}**",
              f"- Files containing raw hex colors: **{debt['files_with_raw_hex_colors']}**",
              f"- Files importing legacy `centermanager.ui.styles`: **{debt['files_importing_legacy_styles']}**",
              f"- Files importing `design_system.tokens`: **{debt['files_importing_design_tokens']}**",
              "", "### File-level signals", ""]
    debt_files = [item for item in files if item["stylesheet_calls"] or item["raw_hex_colors"] or item["imports_legacy_styles"] or item["parse_error"]]
    lines += _markdown_table(
        ["Source", "setStyleSheet", "Raw colors", "Legacy styles", "Parse error"],
        ((item["path"], item["stylesheet_calls"], ", ".join(item["raw_hex_colors"]) or "—", "yes" if item["imports_legacy_styles"] else "no", item["parse_error"] or "—") for item in debt_files),
    )

    errors = [item for item in files if item["parse_error"]]
    if errors:
        lines += ["", "## Parse errors", "", "Inventory is incomplete until these files parse successfully:", ""]
        lines += [f"- `{item['path']}` — {item['parse_error']}" for item in errors]

    lines += ["", "## Regenerate", "", "```bash", "cd CenterManager", "python scripts/ui_inventory.py --write", "python scripts/ui_inventory.py --check", "```", ""]
    return "\n".join(lines)


def _canonical_json(inventory: dict) -> str:
    return json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _check_text(path: Path, expected: str) -> bool:
    if not path.exists():
        print(f"STALE: {path} does not exist")
        return False
    actual = path.read_text(encoding="utf-8")
    if actual != expected:
        print(f"STALE: {path}")
        return False
    return True


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    root = _project_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ui-root", type=Path, default=_default_ui_root())
    parser.add_argument("--json-output", type=Path, default=root / "docs" / "ui_baseline" / "ui_inventory.json")
    parser.add_argument("--markdown-output", type=Path, default=root / "docs" / "ui_baseline" / "UI_INVENTORY.md")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="Write JSON and Markdown snapshots.")
    mode.add_argument("--check", action="store_true", help="Fail if checked-in snapshots are stale.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    inventory = scan_ui(args.ui_root)
    json_text = _canonical_json(inventory)
    markdown_text = render_markdown(inventory)
    if args.write:
        _write_text(args.json_output, json_text)
        _write_text(args.markdown_output, markdown_text)
        print(f"Wrote {args.json_output}")
        print(f"Wrote {args.markdown_output}")
        return 0
    if args.check:
        ok = _check_text(args.json_output, json_text)
        ok = _check_text(args.markdown_output, markdown_text) and ok
        return 0 if ok else 1
    print(json_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
