"""Portable CSV metadata for Income/Expense vouchers; never export local paths."""
from __future__ import annotations


def _safe_cell(value: str) -> str:
    cell = " ".join(str(value or "").splitlines()).strip()
    if cell.lstrip().startswith(("=", "+", "-", "@")):
        cell = "'" + cell
    return cell


def voucher_csv_fields(attachments) -> tuple[int, str, str]:
    rows = list(attachments)
    return (
        len(rows),
        " | ".join(_safe_cell(a.original_filename) for a in rows),
        " | ".join(str(a.sha256 or "") for a in rows),
    )
