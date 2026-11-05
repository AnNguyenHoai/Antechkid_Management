"""RV-01: static inventory safety and classification tests; no production DB imports."""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "audit_recovery_mutations.py"


def _load():
    spec = importlib.util.spec_from_file_location("rv01_mutation_scan_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ast_inventory_detects_commit_sql_file_and_audit_calls_without_execution(tmp_path, monkeypatch):
    scanner = _load()
    root = tmp_path / "src" / "centermanager"
    source = root / "services" / "synthetic.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "def mutate(s, path, audit):\n"
        "    s.execute('INSERT INTO audit_rows(x) VALUES (1)')\n"
        "    audit.record_in_session(s, 'CREATE', 'test')\n"
        "    s.commit()\n"
        "    path.write_bytes(b'safe')\n"
        "\n"
        "def read(s):\n"
        "    return s.execute('SELECT 1')\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(scanner, "PROJECT", root)
    sites = scanner.scan(source)
    pairs = {(row["category"], row["function"]) for row in sites}
    assert ("SQL_MUTATION_LITERAL", "mutate") in pairs
    assert ("AUDIT_IN_TRANSACTION", "mutate") in pairs
    assert ("DATABASE_COMMIT", "mutate") in pairs
    assert ("FILE_WRITE", "mutate") in pairs
    assert ("SQL_EXECUTE_REVIEW", "read") in pairs
    assert all(row["classification"] == "UNREVIEWED" for row in sites)


def test_ast_inventory_does_not_execute_synthetic_source(tmp_path, monkeypatch):
    scanner = _load()
    root = tmp_path / "src" / "centermanager"
    file = root / "services" / "no_run.py"
    file.parent.mkdir(parents=True)
    marker = tmp_path / "must_not_exist"
    file.write_text(
        "from pathlib import Path\n"
        "Path(" + repr(str(marker)) + ").write_text('this must never run')\n"
        "def example(s):\n"
        "    s.commit()\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(scanner, "PROJECT", root)
    sites = scanner.scan(file)
    assert {s["category"] for s in sites} >= {"FILE_WRITE", "DATABASE_COMMIT"}
    assert not marker.exists(), "AST audit executed untrusted application code"


def test_ast_inventory_current_source_contains_known_risk_boundaries():
    scanner = _load()
    services = scanner.PROJECT / "services"
    expected = {
        "permission_service.py": {"DATABASE_COMMIT", "AUDIT_POSSIBLY_SEPARATE"},
        "attendance_service.py": {"DATABASE_COMMIT"},
        "finance_attachment_service.py": {"DATABASE_COMMIT", "AUDIT_IN_TRANSACTION"},
        "configuration_service.py": {"CONFIG_WRITE"},
    }
    for filename, categories in expected.items():
        file = services / filename
        assert file.exists(), f"Missing audited source: {filename}"
        observed = {row["category"] for row in scanner.scan(file)}
        assert categories <= observed, f"{filename}: expected {categories}, got {observed}"


def test_ast_inventory_sql_string_scan_never_interprets_code():
    scanner = _load()
    malicious = "def run(db):\n    db.execute('DELETE FROM student')\n"
    parsed = ast.parse(malicious)
    assert any(isinstance(node, ast.Call) for node in ast.walk(parsed))
    assert scanner.name_of(ast.parse("s.commit()", mode="eval").body.func) == "s.commit"
