"""Conservative cross-generation student/class reconciliation for course-based tuition.

Natural identities are used *only* when unique in both independently verified
snapshots. Otherwise UNKNOWN, never a guessed match or replay instruction.
All SQL is allowlisted read-only. No hidden default to auto-increment IDs.
"""
from __future__ import annotations

from collections import Counter
from decimal import Decimal

_IDENTITIES = {
    "students": (("student_code",), ("full_name", "status", "deleted_at")),
    "classes": (("name", "course"), ("status", "course_fee", "planned_sessions", "deleted_at")),
}
_MAX_ROWS = 20000


def _load(db, table, fields):
    columns = {r[1] for r in db.execute("PRAGMA table_info(" + table + ")")}
    if not set(("id", *fields)).issubset(columns):
        return None
    rows = db.execute(
        "SELECT " + ", ".join(("id", *fields)) + " FROM " + table
        + " LIMIT " + str(_MAX_ROWS + 1)
    ).fetchall()
    if len(rows) > _MAX_ROWS:
        return None
    return [{"id": r[0], **{k: r[j + 1] for j, k in enumerate(fields)}} for r in rows]


def _value(field, value):
    if value is None:
        return None
    if field in ("monthly_fee_vnd", "amount_vnd", "course_fee"):
        return str(Decimal(str(value)).quantize(Decimal("0.0001")))
    return str(value)


def _matching(old, main, identity, values, kind):
    counts_old = Counter(tuple(str(row.get(k)) for k in identity) for row in old)
    counts_main = Counter(tuple(str(row.get(k)) for k in identity) for row in main)
    lookup = {tuple(str(row.get(k)) for k in identity): row for row in main}
    results = []
    crosswalk = {}
    for row in old:
        key = tuple(str(row.get(k)) for k in identity)
        result = {"entity": kind, "recovery_row_id": row["id"],
                  "identity": {k: _value(k, row[k]) for k in identity}}
        if any(row.get(k) is None or str(row[k]).strip() == "" for k in identity):
            status, reason = "UNKNOWN", "INCOMPLETE_STABLE_IDENTITY"
        elif counts_old[key] != 1 or counts_main[key] > 1:
            status, reason = "UNKNOWN", "AMBIGUOUS_STABLE_IDENTITY"
        elif key not in lookup:
            status, reason = "NOT_FOUND", "UNIQUE_NATURAL_KEY_ABSENT_IN_MAIN"
        else:
            match = lookup[key]
            diff = [k for k in values if _value(k, row.get(k)) != _value(k, match.get(k))]
            result["main_row_id"] = match["id"]
            if diff:
                status, reason = "PRESENT_DIFFERENT", "FIELDS_DIFFER"
                result["changed_fields"] = diff
                result["recovery_values"] = {k: _value(k, row[k]) for k in diff}
                result["main_values"] = {k: _value(k, match[k]) for k in diff}
            else:
                status, reason = "PRESENT_IDENTICAL", "FIELDS_MATCH"
            crosswalk[row["id"]] = match["id"]
        result["status"] = status
        result["reason"] = reason
        results.append(result)
    return results, crosswalk


def compare_business_identities(old_db, main_db):
    """Compare uniquely identified students/classes/plans; all else UNKNOWN."""
    findings = []
    mapping = {}
    for kind, (identity, values) in _IDENTITIES.items():
        fields = (*identity, *values)
        a, b = _load(old_db, kind, fields), _load(main_db, kind, fields)
        if a is None or b is None:
            findings.append({"entity": kind, "status": "UNKNOWN", "reason": "SCHEMA_INCOMPATIBLE"})
            mapping[kind] = {}
            continue
        results, crosswalk = _matching(a, b, identity, values, kind)
        findings.extend(results)
        mapping[kind] = crosswalk

    return {
        "findings": findings,
        "mapped_classes": len(mapping["classes"]),
        "coverage": "STUDENT_CLASS_NATURAL_KEYS_ONLY",
    }



def wallet_movements(db):
    """Realized income/expense movement only, NOT opening/closing wallet balances.

    Dates, filters and unknown aliases follow WalletService ledger semantics.
    A missing required field or unknown alias returns UNKNOWN rather than
    omitting payments and displaying a false financial total.
    """
    from centermanager.core.wallet import resolve_wallet

    income_fields = ("amount", "payment_method", "status", "deleted_at")
    expense_fields = ("amount", "payment_method", "status", "deleted_at")
    incomes = _load(db, "incomes", income_fields)
    expenses = _load(db, "expenses", expense_fields)
    if incomes is None or expenses is None:
        return {"status": "UNKNOWN", "reason": "SCHEMA_INCOMPATIBLE"}
    values = {"CASH": Decimal("0"), "BANK": Decimal("0")}
    try:
        for item in incomes:
            if item["deleted_at"] is None and item["status"] == "ACTIVE":
                wallet = resolve_wallet(item["payment_method"]).value
                values[wallet] += Decimal(str(item["amount"]))
        for item in expenses:
            if item["deleted_at"] is None and item["status"] in ("Completed", "Paid"):
                wallet = resolve_wallet(item["payment_method"]).value
                values[wallet] -= Decimal(str(item["amount"]))
    except (ValueError, TypeError, ArithmeticError, KeyError, AttributeError) as exc:
        return {"status": "UNKNOWN", "reason": "UNRESOLVED_LEDGER_ALIAS_OR_AMOUNT"}
    return {
        "status": "PARTIAL_MOVEMENT_ONLY",
        "cash_delta": str(values["CASH"].quantize(Decimal("0.01"))),
        "bank_delta": str(values["BANK"].quantize(Decimal("0.01"))),
        "warning": "Chỉ là tổng biến động thu/chi, KHÔNG phải số dư ví; chưa gồm số dư đầu kỳ.",
    }


def outstanding_coverage():
    """Explicit gate until canonical accrual can be reproduced on old schema."""
    return {
        "status": "UNKNOWN",
        "reason": "CANONICAL_ACCRUAL_REQUIRED",
        "warning": (
            "Không tự suy đoán công nợ từ tiền thu. Cần toàn bộ lịch học, "
            "bản phân bổ, học bù và các lần điều chỉnh để tính chính xác."
        ),
    }
