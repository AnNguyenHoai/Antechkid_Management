"""Portable finance CSV/ZIP export without database migration."""
import hashlib
import io
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest
from centermanager.services import finance_csv_vouchers as vouchers


def test_csv_metadata_is_injection_safe():
    first = SimpleNamespace(original_filename="=HYPERLINK(A1).pdf", sha256="1" * 64)
    second = SimpleNamespace(original_filename="receipt.pdf", sha256="2" * 64)
    assert vouchers.voucher_csv_fields([first, second]) == (
        2, "'=HYPERLINK(A1).pdf | receipt.pdf", "1" * 64 + " | " + "2" * 64,
    )


def test_zip_contains_original_document_and_csv(tmp_path, monkeypatch):
    source = tmp_path / "Attachment" / "Finance" / "2026" / "11"
    source.mkdir(parents=True)
    file = source / "receipt.pdf"
    file.write_bytes(b"%PDF-1.7 test invoice")
    item = SimpleNamespace(
        id=11, original_filename="receipt.pdf",
        stored_path="Finance/2026/11/receipt.pdf",
        sha256=hashlib.sha256(file.read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(vouchers, "get_paths", lambda: SimpleNamespace(
        attachment_dir=tmp_path / "Attachment"))
    destination = tmp_path / "output.zip"
    vouchers.write_voucher_zip(destination, "Transaction ID\n101\n", "INCOME", {101: [item]})
    with zipfile.ZipFile(destination) as archive:
        assert archive.read("transactions.csv").decode("utf-8-sig") == "Transaction ID\n101\n"
        assert archive.read("vouchers/INCOME_101/11_receipt.pdf") == file.read_bytes()


def test_tampered_document_refuses_complete_zip(tmp_path, monkeypatch):
    root = tmp_path / "Attachment"
    root.mkdir()
    (root / "receipt.pdf").write_bytes(b"changed")
    monkeypatch.setattr(vouchers, "get_paths", lambda: SimpleNamespace(attachment_dir=root))
    item = SimpleNamespace(id=1, original_filename="receipt.pdf",
                           stored_path="receipt.pdf", sha256="0" * 64)
    destination = tmp_path / "reject.zip"
    with pytest.raises(ValueError, match="checksum"):
        vouchers.write_voucher_zip(destination, "Transaction ID\n1\n", "EXPENSE", {1: [item]})
    assert not destination.exists()


def test_missing_voucher_refuses_zip(tmp_path, monkeypatch):
    monkeypatch.setattr(vouchers, "get_paths", lambda: SimpleNamespace(attachment_dir=tmp_path))
    item = SimpleNamespace(id=1, original_filename="receipt.jpg",
                           stored_path="missing.jpg", sha256="0" * 64)
    with pytest.raises(FileNotFoundError):
        vouchers.write_voucher_zip(tmp_path / "missing.zip", "", "INCOME", {1: [item]})
    assert not (tmp_path / "missing.zip").exists()


def test_export_services_and_views_reference_vouchers_without_new_schema():
    root = Path(__file__).resolve().parents[1] / "src/centermanager"
    for filename in ("income_service.py", "expense_service.py"):
        content = (root / "services" / filename).read_text(encoding="utf-8")
        assert "Voucher Count" in content
        assert "Voucher Filenames" in content
        assert "Voucher SHA256" in content
        assert "write_voucher_zip" in content
    for filename in ("income_list_page.py", "expense_list_page.py"):
        content = (root / "ui/finance_workspace" / filename).read_text(encoding="utf-8")
        assert "Xuất ZIP + chứng từ" in content
