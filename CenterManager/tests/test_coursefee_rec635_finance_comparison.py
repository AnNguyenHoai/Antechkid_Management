"""REC-635: finance comparisons must never imply missing transaction without evidence."""
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.platform.recovery_finance_compare import (
    compare_finance_connections, compare_verified_case, render_report_json,
    write_secure_report,
)


def _db():
    connection = sqlite3.connect(":memory:")
    connection.execute(
        "CREATE TABLE incomes (id INTEGER PRIMARY KEY, idempotency_key TEXT, "
        "student_id INTEGER, class_id INTEGER, enrollment_id INTEGER, "
        "amount REAL, income_type TEXT, payment_method TEXT, payment_date TEXT, "
        "payment_period TEXT, finance_period_id INTEGER, status TEXT, deleted_at TEXT)"
    )
    connection.execute(
        "CREATE TABLE expenses (id INTEGER PRIMARY KEY, idempotency_key TEXT, "
        "category TEXT, amount REAL, payment_method TEXT, status TEXT, "
        "payment_date TEXT, finance_period_id INTEGER, funding_source TEXT, "
        "incurred_date TEXT, deleted_at TEXT)"
    )
    connection.execute(
        "CREATE TABLE tuition_adjustments (id INTEGER PRIMARY KEY, "
        "idempotency_key TEXT, enrollment_id INTEGER, origin_income_id INTEGER, "
        "origin_adjustment_id INTEGER, linked_income_id INTEGER, kind TEXT, "
        "amount REAL, adjustment_date TEXT, wallet TEXT)"
    )
    return connection


def _income(db, rid, key, amount=1200000):
    db.execute(
        "INSERT INTO incomes (id,idempotency_key,student_id,amount,"
        "income_type,payment_method,payment_date,status) VALUES (?,?,?,?,?,?,?,?)",
        (rid, key, 42, amount, "Tuition", "CASH", "2026-11-09", "ACTIVE"),
    )


def test_present_identical_and_changed_are_keyed_not_autoincrement():
    old, main = _db(), _db()
    _income(old, 1, "receipt-abc")
    _income(main, 999, "receipt-abc")
    _income(old, 2, "receipt-xyz")
    _income(main, 7, "receipt-xyz", 900000)
    result = [x for x in compare_finance_connections(old, main) if x["table"] == "incomes"]
    assert [x["status"] for x in result] == ["UNKNOWN", "PRESENT_DIFFERENT"]
    assert result[0]["reason"] == "UNVERIFIED_CROSS_GENERATION_RELATIONSHIPS"
    assert result[0]["main_row_id"] == 999
    assert result[1]["changed_fields"] == ["amount"]
    assert result[1]["recovery"]["amount"] == "1200000.0000"
    assert result[1]["main"]["amount"] == "900000.0000"


def test_not_found_is_snapshot_only_and_id_reuse_is_unknown():
    old, main = _db(), _db()
    _income(old, 1, "old-stable-key")
    _income(old, 2, "another-key")
    _income(main, 1, "a-different-transaction")
    result = [x for x in compare_finance_connections(old, main) if x["table"] == "incomes"]
    assert [x["status"] for x in result] == ["UNKNOWN", "NOT_FOUND"]
    assert result[0]["reason"] == "ROW_ID_REUSED"
    assert result[1]["reason"] == "KEY_NOT_FOUND_IN_VERIFIED_SNAPSHOT"


def test_missing_and_duplicate_idempotency_are_unknown():
    old, main = _db(), _db()
    _income(old, 1, None)
    _income(old, 2, "duplicate-key")
    _income(main, 3, "duplicate-key")
    _income(main, 4, "duplicate-key")
    result = [x for x in compare_finance_connections(old, main) if x["table"] == "incomes"]
    assert [x["status"] for x in result] == ["UNKNOWN", "UNKNOWN"]
    assert result[0]["reason"] == "NO_STABLE_KEY"
    assert result[1]["reason"] == "AMBIGUOUS_IDEMPOTENCY_KEY"


def test_missing_schema_is_unknown_never_not_found():
    old, main = _db(), sqlite3.connect(":memory:")
    result = compare_finance_connections(old, main)
    assert len(result) == 3
    assert all(item["status"] == "UNKNOWN" for item in result)


def test_finance_role_checked_before_backup_access():
    class ForbiddenRegistry:
        def get(self, _):
            raise AssertionError("read recovery without role")
    with pytest.raises(PermissionError):
        compare_verified_case(ForbiddenRegistry(), "x", provider=None, can_view_finance=False)


def test_explicit_file_export_and_no_automatic_plaintext(tmp_path):
    output = tmp_path / "finance-compare.json"
    assert not output.exists()
    write_secure_report(output, render_report_json({
        "coverage": "PARTIAL_KEYED_COURSE_FEE_LEDGER_ONLY",
        "findings": [{"status": "UNKNOWN"}],
    }))
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["findings"][0]["status"] == "UNKNOWN"
    assert data["coverage"].startswith("PARTIAL")
    assert not list(tmp_path.glob("*.tmp"))


def test_no_foreign_ids_can_prove_identical_finance_values():
    old, main = _db(), _db()
    for db, rid in ((old, 1), (main, 99)):
        db.execute(
            "INSERT INTO expenses (id,idempotency_key,category,amount,"
            "payment_method,status,payment_date) "
            "VALUES (?, 'shared-txn', 'Equipment', 500000, 'CASH', 'Completed', '2026-11-10')",
            (rid,),
        )
    result = [r for r in compare_finance_connections(old, main) if r["table"] == "expenses"]
    assert result[0]["status"] == "PRESENT_IDENTICAL"


def test_same_raw_foreign_id_is_not_proof_of_same_student():
    old, main = _db(), _db()
    _income(old, 3, "same-idempotency-key")
    _income(main, 99, "same-idempotency-key")
    result = [r for r in compare_finance_connections(old, main) if r["table"] == "incomes"]
    assert result[0]["status"] == "UNKNOWN"
    assert result[0]["unverified_relationship_fields"] == ["student_id"]


def test_changed_amount_remains_visible_even_when_foreign_identity_unknown():
    old, main = _db(), _db()
    _income(old, 3, "shared-key", 1200000)
    _income(main, 44, "shared-key", 900000)
    result = [r for r in compare_finance_connections(old, main) if r["table"] == "incomes"]
    assert result[0]["status"] == "PRESENT_DIFFERENT"
    assert result[0]["changed_fields"] == ["amount"]
    assert result[0]["unverified_relationship_fields"] == ["student_id"]


def test_encrypted_main_worktree_requires_clean_git_database_and_identity(tmp_path):
    from centermanager.platform.recovery_finance_compare import _assert_git_main_artifact_clean
    root = tmp_path / "repo"
    path = root / "database" / "center.db"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"synthetic")
    calls = []
    class Provider:
        _repo_path = root
        def _run_git_command(self, args):
            calls.append(args)
            return ""
    provider = Provider()
    _assert_git_main_artifact_clean(provider, path, encrypted=True)
    assert calls and "database/center.db.identity.json" in calls[0]
    provider._run_git_command = lambda args: " M database/center.db"
    with pytest.raises(ValueError, match="dirty/untracked"):
        _assert_git_main_artifact_clean(provider, path, encrypted=True)


def test_encrypted_main_worktree_rejects_external_file_and_missing_provenance(tmp_path):
    from centermanager.platform.recovery_finance_compare import _assert_git_main_artifact_clean
    root = tmp_path / "repo"
    with pytest.raises(ValueError, match="cannot authenticate"):
        _assert_git_main_artifact_clean(object(), tmp_path / "main.db", encrypted=True)
    provider = SimpleNamespace(_repo_path=root, _run_git_command=lambda _: "")
    with pytest.raises(ValueError, match="not from the verified Git checkout"):
        _assert_git_main_artifact_clean(provider, tmp_path / "main.db", encrypted=True)


def test_coursefee_recovery_has_only_legacy_finance_ledgers():
    old, main = _db(), _db()
    results = compare_finance_connections(old, main)
    assert {item["table"] for item in results} == {
        "incomes", "expenses", "tuition_adjustments",
    }
    assert not any("monthly" in item["table"] for item in results)
