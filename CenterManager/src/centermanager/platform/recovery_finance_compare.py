"""On-demand, read-only comparison of verified recovery finance transactions.

An absent MAIN idempotency key is NOT proof of lost money. This module never
copies, merges, publishes, replays or modifies either database. Only a caller
with finance.view permission may request a comparison. The production entry
point independently checks the remote and local Git MAIN commit before reads.
"""
from __future__ import annotations

import json
import os
import uuid
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
# These are integer foreign keys local to each database generation. A numerically
# equal ID is not proof of the same student, class, enrollment, session or ledger
# entry after fresh DB import. Never use raw equality to claim business identity.
_LOCAL_RELATION_FIELDS = {
    "student_id", "class_id", "enrollment_id", "finance_period_id",
    "origin_income_id", "origin_adjustment_id", "linked_income_id",
    "session_id", "replacement_session_id",
}
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
                    concrete_changes = [
                        field for field in changed if field not in _LOCAL_RELATION_FIELDS
                    ]
                    relations_present = [
                        field for field in _FIELDS[table]
                        if field in _LOCAL_RELATION_FIELDS
                        and (entry[field] is not None or match[field] is not None)
                    ]
                    if concrete_changes:
                        status, reason = STATUS_DIFFERENT, "VERIFIED_KEY_NON_RELATIONAL_FIELDS_DIFFER"
                    elif relations_present:
                        status, reason = STATUS_UNKNOWN, "UNVERIFIED_CROSS_GENERATION_RELATIONSHIPS"
                    else:
                        status, reason = STATUS_IDENTICAL, "VALUES_MATCH"
                    if changed:
                        finding["changed_fields"] = changed
                    if relations_present:
                        finding["unverified_relationship_fields"] = relations_present
                        finding["relationship_warning"] = (
                            "IDs are database-local; equal numbers do not prove "
                            "the same related business record across generations."
                        )
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


def _assert_git_main_artifact_clean(provider, main_path: Path, *, encrypted: bool):
    """Refuse dirty/untracked Git MAIN DB and signed identity in production.

    A matching HEAD/OID alone never proves the working-tree file is the
    committed MAIN. Read-only Git status checks the exact two artifacts.
    """
    if not encrypted:
        return  # Historical plain SQLite tests are not production deployments.
    repo = getattr(provider, "_repo_path", None)
    run = getattr(provider, "_run_git_command", None)
    if repo is None or not callable(run):
        raise ValueError("Git provider cannot authenticate MAIN worktree")
    expected = (Path(repo) / "database" / "center.db").resolve()
    if Path(main_path).resolve() != expected:
        raise ValueError("MAIN DB is not from the verified Git checkout")
    changes = run([
        "status", "--porcelain", "--untracked-files=normal", "--",
        "database/center.db", "database/center.db.identity.json",
    ])
    if not isinstance(changes, str) or changes.strip():
        raise ValueError("Git MAIN DB or signed identity is dirty/untracked")


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
    _assert_git_main_artifact_clean(provider, main_path, encrypted=encrypted)
    old_key = DatabaseKeyStore(source / "database_key.dpapi").load() if encrypted else None
    main_key = DatabaseKeyStore().load() if encrypted else None
    validate_database_artifact(old_path, encryption_required=encrypted, key=old_key)
    validate_database_artifact(main_path, encryption_required=encrypted, key=main_key)
    if encrypted:
        validate_identity(main_path, main_key)
    with _immutable_reader(old_path, old_key) as recovery_db:
        with _immutable_reader(main_path, main_key) as main_db:
            findings = compare_finance_connections(recovery_db, main_db)
            from centermanager.platform.recovery_business_compare import (
                compare_business_identities, wallet_movements, outstanding_coverage,
            )
            business = compare_business_identities(recovery_db, main_db)
            wallets = {
                "recovery": wallet_movements(recovery_db),
                "main": wallet_movements(main_db),
            }
            debt = outstanding_coverage()
    # Reverify file identities after reading, not just branch OIDs.
    registry.journal.verify_capture(source)
    validate_database_artifact(main_path, encryption_required=encrypted, key=main_key)
    if encrypted:
        validate_identity(main_path, main_key)
    _assert_git_main_artifact_clean(provider, main_path, encrypted=encrypted)
    if provider.get_local_main_commit() != local or provider.observe_remote_main_commit() != observed:
        raise ValueError("Git MAIN changed during comparison: discard result")
    return {
        "case_id": case_id,
        "compared_main_oid": observed,
        "coverage": "PARTIAL_KEYED_COURSE_FEE_LEDGER_ONLY",
        "publication": case.get("publication", "UNVERIFIED"),
        "warning": (
            "NOT_FOUND không chứng minh giao dịch đã mất. "
            "Phải đối chiếu học sinh, học phí, ví và công nợ trước khi nhập lại. "
            "Không so sánh trực tiếp số dư hoặc giao dịch thiếu idempotency key."
        ),
        "findings": findings,
        "business_identities": business,
        "wallet_movements": wallets,
        "outstanding_coverage": debt,
    }


def compare_verified_notice(notices, notice: dict, *, provider, can_view_finance: bool):
    """Modern Git MAIN-first review notice: signed old DB/WAL, never raw rollback."""
    if not can_view_finance:
        raise PermissionError("finance.view permission required")
    from centermanager.platform.recovery_rollback_evidence import (
        verify_startup_rollback, reconstructed_readonly_snapshot,
    )
    from centermanager.database.artifact_security import (
        validate_authoritative_repository_database, validate_database_artifact,
    )
    from centermanager.database.artifact_identity import validate_identity
    from centermanager.database.encryption import (
        DatabaseKeyStore, database_encryption_required,
    )

    verified_notice = notices.validate_notice(
        notices.root / (notice["id"] + ".json")
    )
    if verified_notice != notice:
        raise ValueError("Recovery review notice changed")
    # Never silently read an unbound startup-rollback generation.
    verify_startup_rollback(notices, notice)

    fetched = provider.get_fetched_remote_main_commit()
    local = provider.get_local_main_commit()
    observed = provider.observe_remote_main_commit()
    if not fetched or fetched != local or fetched != observed:
        raise ValueError("Git MAIN cannot be independently verified")

    main_path = validate_authoritative_repository_database()
    encrypted = database_encryption_required()
    _assert_git_main_artifact_clean(provider, main_path, encrypted=encrypted)
    main_key = DatabaseKeyStore().load() if encrypted else None
    with reconstructed_readonly_snapshot(notices, notice) as (recovery_path, old_key):
        validate_database_artifact(
            recovery_path, encryption_required=encrypted, key=old_key
        )
        with _immutable_reader(recovery_path, old_key) as recovery_db:
            with _immutable_reader(main_path, main_key) as main_db:
                findings = compare_finance_connections(recovery_db, main_db)
                from centermanager.platform.recovery_business_compare import (
                    compare_business_identities, wallet_movements, outstanding_coverage,
                )
                business = compare_business_identities(recovery_db, main_db)
                wallets = {
                    "recovery": wallet_movements(recovery_db),
                    "main": wallet_movements(main_db),
                }
                debt = outstanding_coverage()
    # The snapshot context has reverified the original signed bytes.
    validate_database_artifact(main_path, encryption_required=encrypted, key=main_key)
    if encrypted:
        validate_identity(main_path, main_key)
    _assert_git_main_artifact_clean(provider, main_path, encrypted=encrypted)
    if provider.get_local_main_commit() != local or provider.observe_remote_main_commit() != observed:
        raise ValueError("MAIN changed during finance comparison")
    return {
        "notice_id": notice["id"],
        "compared_main_oid": observed,
        "coverage": "PARTIAL_KEYED_COURSE_FEE_LEDGER_ONLY",
        "publication": "UNVERIFIED",
        "warning": (
            "Đây là so sánh DB local trước startup với MAIN hiện tại, không phải "
            "danh sách các khoản chắc chắn bị mất. NOT_FOUND chỉ là thiếu khóa "
            "idempotency trong snapshot MAIN vừa xác thực. "
            "Không nhập lại khoản thu/chi nếu chưa kiểm tra trùng, ví và công nợ."
        ),
        "findings": findings,
        "business_identities": business,
        "wallet_movements": wallets,
        "outstanding_coverage": debt,
    }


def render_report_json(report: dict) -> str:
    """Explicitly exported sensitive finance data; caller enforces permission."""
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_secure_report(destination: Path, content: str) -> None:
    """User-triggered atomic export; no implicit temporary plaintext at startup.

    File system ACLs are platform-dependent: caller must show the privacy warning.
    """
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name("." + target.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        fd = os.open(str(temp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)
