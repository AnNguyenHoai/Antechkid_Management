#!/usr/bin/env python3
"""RV-01 read-only mutation-site inventory.

Usage:
    python CenterManager/tools/audit_recovery_mutations.py
    python CenterManager/tools/audit_recovery_mutations.py --json /tmp/mutations.json

This script uses only Python AST and reads code. It does not import application
modules, open SQLCipher databases, run Git, write application data, or assert
that a matching AST node is an applied business mutation.

A static report is a review queue, NOT proof of complete runtime coverage:
dynamic dispatch, native extensions, SQL triggers, and reflection require
manual source tracing and integration tests.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1] / "src" / "centermanager"
ROOTS = ("services", "repositories", "ui", "database", "platform", "events")

MUTATION_CALLS = {
    "commit": "DATABASE_COMMIT",
    "flush": "DATABASE_FLUSH",
    "bulk_save_objects": "DATABASE_BULK",
    "bulk_insert_mappings": "DATABASE_BULK",
    "bulk_update_mappings": "DATABASE_BULK",
    "executemany": "SQL_EXECUTE_REVIEW",
    "executescript": "SQL_EXECUTE_REVIEW",
    "execute": "SQL_EXECUTE_REVIEW",
    "connect": "CONNECTION_REVIEW",
    "write_text": "FILE_WRITE",
    "write_bytes": "FILE_WRITE",
    "copy2": "FILE_COPY",
    "copyfile": "FILE_COPY",
    "copytree": "FILE_COPY",
    "replace": "FILE_REPLACE_REVIEW",
    "unlink": "FILE_DELETE",
    "remove": "FILE_DELETE_REVIEW",
    "save_config": "CONFIG_WRITE",
    "publish_only": "GIT_PUBLICATION",
    "publish_database": "GIT_PUBLICATION",
    "record_in_session": "AUDIT_IN_TRANSACTION",
    "record": "AUDIT_POSSIBLY_SEPARATE",
}

DANGEROUS_SQL = (
    "insert ", "update ", "delete ", "replace ", "create ", "alter ",
    "drop ", "truncate ", "vacuum ", "pragma ",
)


def name_of(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = name_of(node.value)
        return (parent + "." if parent else "") + node.attr
    return ""


def owner_of(tree: ast.AST, lineno: int) -> str:
    owner = "(module)"
    best = (0, 10**12)
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(n, "end_lineno", n.lineno)
            if n.lineno <= lineno <= end and (end - n.lineno) < best[1]:
                owner = n.name
                best = (n.lineno, end - n.lineno)
    return owner


def scan(path: Path) -> list[dict]:
    relative = path.relative_to(PROJECT.parent.parent).as_posix()
    source = path.read_text(encoding="utf-8-sig")
    tree = ast.parse(source, filename=str(path))
    rows: list[dict] = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        called = name_of(n.func)
        terminal = called.rsplit(".", 1)[-1]
        category = MUTATION_CALLS.get(terminal)
        if category is None:
            continue
        if terminal in {"execute", "executemany", "executescript"}:
            if n.args and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
                sql = n.args[0].value.lower().lstrip()
                category = "SQL_MUTATION_LITERAL" if sql.startswith(DANGEROUS_SQL) else "SQL_EXECUTE_REVIEW"
        rows.append({
            "file": relative,
            "line": n.lineno,
            "function": owner_of(tree, n.lineno),
            "category": category,
            "call": called,
            "classification": "UNREVIEWED",
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, help="write a UTF-8 JSON review queue")
    args = parser.parse_args()
    rows: list[dict] = []
    parse_errors = []
    scanned_files = 0
    for dirname in ROOTS:
        folder = PROJECT / dirname
        if not folder.is_dir():
            continue
        for file in sorted(folder.rglob("*.py")):
            scanned_files += 1
            try:
                rows.extend(scan(file))
            except (OSError, SyntaxError, UnicodeError) as exc:
                parse_errors.append({"file": str(file.relative_to(PROJECT.parent.parent)), "error": type(exc).__name__})
    rows.sort(key=lambda row: (row["file"], row["line"], row["category"]))
    result = {
        "schema": "rv-01-audit-static-v1",
        "scanned_files": scanned_files,
        "candidate_calls": len(rows),
        "parse_errors": parse_errors,
        "warning": "Candidate calls, NOT a complete or verified mutation coverage claim.",
        "sites": rows,
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Review queue: {args.json}")
    else:
        print(json.dumps({k: v for k, v in result.items() if k != "sites"}, indent=2))
        for row in rows:
            print(f'{row["category"]:<23} {row["file"]}:{row["line"]} {row["function"]} {row["call"]}')
    return 1 if parse_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
