"""Voucher CSV metadata backport: no tuition schema migration required."""
from types import SimpleNamespace

from centermanager.services.finance_csv_vouchers import voucher_csv_fields


def test_voucher_export_no_attachments():
    assert voucher_csv_fields([]) == (0, "", "")


def test_voucher_export_counts_and_prevents_spreadsheet_formula_injection():
    attachments = [
        SimpleNamespace(original_filename="=HYPERLINK(test).pdf", sha256="abc"),
        SimpleNamespace(original_filename="invoice.pdf", sha256="def"),
    ]
    assert voucher_csv_fields(attachments) == (
        2, "'=HYPERLINK(test).pdf | invoice.pdf", "abc | def",
    )


def test_finance_exports_reference_vouchers_without_new_migration():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "src/centermanager"
    for module in ("expense_service.py", "income_service.py"):
        content = (root / "services" / module).read_text(encoding="utf-8")
        assert "voucher_csv_fields" in content
        assert "Voucher Count" in content
        assert "Voucher SHA256" in content
    repo = (root / "repositories/finance_attachment_repository.py").read_text(encoding="utf-8")
    assert "def list_active_for" in repo
