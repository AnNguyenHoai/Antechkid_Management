"""On-demand, read-only comparison of verified recovery finance transactions.

An absent MAIN idempotency key is NOT proof of lost money. This module never
copies, merges, publishes, replays or modifies either database. Only a caller
with finance.view permission may request a comparison. The production entry
point independently checks the remote and local Git MAIN commit before reads.
"""
from __future__ import annotations

import json
from collections import Counter
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

STATUS_IDENTICAL = "PRESENT_IDENTICAL"
STATUS_DIFFERENT = "PRESENT_DIFFERENT"
STATUS_MISSING = "NOT_FOUND"
STATUS_UNKNOWN = "UNKNOWN"

# Schema/field allowlist: do not SELECT notes, credentials, personal details.
_FIELDS = {
    "incomes": (
        "idempotency_key", "student_id", "class_id", "enrollment_id",
        "amount", "income_type", "payment_method", "payment_date",
        "payment_period", "finance_period_id", "status", "deleted_at",
    ),
    "expenses": (
        "idempotency_key", "category", "amount", "payment_method",
        "status", "payment_date", "finance_period_id", "funding_source",
        "incurred_date", "deleted_at",
    ),
    "tuition_adjustments": (
        "idempotency_key", "enrollment_id", "origin_income_id",
        "origin_adjustment_id", "linked_income_id", "kind", "amount",
        "adjustment_date", "wallet",
    ),
}
_AMOUNT_FIELDS = {"amount"}
_MAX_ROWS = 20000


def _normalized(key, value):
    if value is None:
        return None
    if key in _AMOUNT_FIELDS:
        return str(Decimal(str(value)).quantize(Decimal("0.0001")))
    return str(value)


def _read_table(connection, table):
    """Allowlisted SELECT only. Schema drift returns UNKNOWN, never NOT_FOUND."""
    allowed = _FIELDS[table]
    columns = {row[1] for row in connection.execute("PRAGMA table_info(" + table + ")")}
    if not set(("id", *allowed)).issubset(columns):
        return None
    projection = ", ".join(("id", *allowed))
    rows = connection.execute(
        "SELECT " + projection + " FROM " + table + " LIMIT " + str(_MAX_ROWS + 1)
    ).fetchall()
    if len(rows) > _MAX_ROWS:
        return None
    return [
        {"id": row[0], **{key: _normalized(key, value) for key, value in zip(allowed, row[1:])}}
        for row in rows
    ]


def compare_finance_connections(recovery_connection, main_connection):
    """Compare transaction snapshots by durable idempotency key, NOT row id.

    NULL/duplicate keys, mismatched id reuse and schema drift are UNKNOWN.
    A NOT_FOUND result means a key is absent in *this verified MAIN snapshot*,
    not that an operator should recreate the financial transaction.
    """
    results = []
    for table in _FIELDS:
        old = _read_table(recovery_connection, table)
        main = _read_table(main_connection, table)
        if old is None or main is None:
            results.append({
                "table": table, "status": STATUS_UNKNOWN,
                "reason": "SCHEMA_MISSING_OR_TOO_MANY_ROWS",
            })
            continue
        count_old = Counter(row["idempotency_key"] for row in old if row["idempotency_key"])
        count_main = Counter(row["idempotency_key"] for row in main if row["idempotency_key"])
        by_key = {row["idempotency_key"]: row for row in main if row["idempotency_key"]}
        by_id = {str(row["id"]): row for row in main}
        for entry in old:
            key = entry["idempotency_key"]
            finding = {
                "table": table,
                "recovery_row_id": entry["id"],
                "idempotency_key": key,
                "recovery": {k: v for k, v in entry.items() if k != "id"},
            }
            if not key:
                status, reason, match = STATUS_UNKNOWN, "NO_STABLE_KEY", None
            elif count_old[key] != 1 or count_main[key] > 1:
                status, reason, match = STATUS_UNKNOWN, "AMBIGUOUS_IDEMPOTENCY_KEY", None
            else:
                match = by_key.get(key)
                if match is None:
                    same_id = by_id.get(str(entry["id"]))
                    if same_id is not None and same_id.get("idempotency_key") != key:
                        status, reason = STATUS_UNKNOWN, "ROW_ID_REUSED"
                    else:
                        status, reason = STATUS_MISSING, "KEY_NOT_FOUND_IN_VERIFIED_SNAPSHOT"
                else:
                    changed = [
                        field for field in _FIELDS[table]
                        if entry[field] != match[field]
                    ]
                    status = STATUS_DIFFERENT if changed else STATUS_IDENTICAL
                    reason = "VALUES_DIFFER" if changed else "VALUES_MATCH"
                    if changed:
                        finding["changed_fields"] = changed
            finding["status"] = status
            finding["reason"] = reason
            if match is not None:
                finding["main_row_id"] = match["id"]
                finding["main"] = {k: v for k, v in match.items() if k != "id"}
            results.append(finding)
    return results


@contextmanager
def _immutable_reader(path: Path, key: bytes | None):
    """Open a standalone, already-validated DB in immutable query-only mode."""
    from centermanager.database.encryption import load_sqlcipher_driver, apply_sqlcipher_key
    from centermanager.database.artifact_security import _assert_standalone_artifact

    _assert_standalone_artifact(path)
    driver = load_sqlcipher_driver() if key is not None else __import__("sqlite3")
    connection = driver.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    try:
        if key is not None:
            apply_sqlcipher_key(connection, key)
        connection.execute("PRAGMA query_only=ON")
        yield connection
    finally:
        connection.close()


def compare_verified_case(registry, case_id: str, *, provider, can_view_finance: bool):
    """Production boundary: authenticated case + snapshot + remote MAIN + role.

    Deliberately fails rather than falling back to unchecked files. Caller
    must invoke from explicit post-login user action, never startup.
    """
    if not can_view_finance:
        raise PermissionError("finance.view permission required")
    case = registry.get(case_id)
    if case is None:
        raise ValueError("No authenticated Recovery Case")
    source = Path(case["capture_ref"])
    manifest = registry.journal.verify_capture(source)
    if manifest.get("files", {}).get("center.db") != case["capture_db_sha256"]:
        raise ValueError("Recovery captured DB fingerprint mismatch")
    old_path = source / "center.db"

    # A local signed DB alone is insufficient: remote authoritative MAIN can
    # have advanced since startup. Never compare to a stale or dirty checkout.
    fetched = provider.get_fetched_remote_main_commit()
    local = provider.get_local_main_commit()
    observed = provider.observe_remote_main_commit()
    if not fetched or fetched != local or fetched != observed:
        raise ValueError("Git MAIN is not independently verified at comparison time")

    from centermanager.database.encryption import (
        DatabaseKeyStore, database_encryption_required,
    )
    from centermanager.database.artifact_security import (
        validate_authoritative_repository_database, validate_database_artifact,
    )
    from centermanager.database.artifact_identity import validate_identity

    main_path = validate_authoritative_repository_database()
    encrypted = database_encryption_required()
    old_key = DatabaseKeyStore(source / "database_key.dpapi").load() if encrypted else None
    main_key = DatabaseKeyStore().load() if encrypted else None
    validate_database_artifact(old_path, encryption_required=encrypted, key=old_key)
    validate_database_artifact(main_path, encryption_required=encrypted, key=main_key)
    if encrypted:
        validate_identity(main_path, main_key)
    with _immutable_reader(old_path, old_key) as recovery_db:
        with _immutable_reader(main_path, main_key) as main_db:
            findings = compare_finance_connections(recovery_db, main_db)
    if provider.get_local_main_commit() != local or provider.observe_remote_main_commit() != observed:
        raise ValueError("Git MAIN changed during comparison: discard result")
    return {
        "case_id": case_id,
        "compared_main_oid": observed,
        "coverage": "PARTIAL_FINANCE_KEYED_TRANSACTIONS_ONLY",
        "publication": case.get("publication", "UNVERIFIED"),
        "warning": (
            "NOT_FOUND không chứng minh giao dịch đã mất. "
            "Phải đối chiếu học sinh, học phí, ví và công nợ trước khi nhập lại. "
            "Không so sánh trực tiếp số dư hoặc dữ liệu không có idempotency key."
        ),
        "findings": findings,
    }


def render_report_json(report: dict) -> str:
    """Explicitly exported sensitive finance data; caller enforces permission."""
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
