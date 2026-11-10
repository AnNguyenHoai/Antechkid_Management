"""Finance CSV voucher metadata and explicit Recovery menu feedback."""
import ast
from pathlib import Path
from types import SimpleNamespace

from centermanager.services.finance_csv_vouchers import voucher_csv_fields

ROOT = Path(__file__).resolve().parents[1] / "src/centermanager"


def test_voucher_metadata_has_count_names_and_sha_without_file_paths():
    rows = [
        SimpleNamespace(original_filename="receipt.pdf", sha256="a" * 64),
        SimpleNamespace(original_filename="=HYPERLINK(1)", sha256="b" * 64),
    ]
    assert voucher_csv_fields(rows) == (
        2, "receipt.pdf | '=HYPERLINK(1)", "a" * 64 + " | " + "b" * 64,
    )
    assert voucher_csv_fields([]) == (0, "", "")


def test_income_and_expense_csv_use_batch_voucher_metadata():
    repo = (ROOT / "repositories/finance_attachment_repository.py").read_text(encoding="utf-8")
    assert "def list_active_for(" in repo
    assert "FinanceAttachment.deleted_at.is_(None)" in repo
    for filename, entity in [("income_service.py", "INCOME"), ("expense_service.py", "EXPENSE")]:
        source = (ROOT / "services" / filename).read_text(encoding="utf-8")
        ast.parse(source)
        export_body = source.split(
            "def export_incomes_csv(" if entity == "INCOME" else "def export_expenses_csv(", 1
        )[1].split("\n    @require_permission", 1)[0]
        assert f'.list_active_for("{entity}",' in export_body
        assert '"Voucher Count", "Voucher Filenames", "Voucher SHA256"' in export_body
        assert "*voucher_csv_fields(" in export_body


def test_recovery_menu_gives_explicit_empty_state_without_restore():
    source = (ROOT / "ui/main_window.py").read_text(encoding="utf-8")
    ast.parse(source)
    assert 'recovery_status.triggered.connect(self._show_recovery_status)' in source
    assert "Không có Recovery nào cần kiểm tra." in source
    assert "Không có log Recovery nào cần kiểm tra." in source
    assert "Không có Recovery Case nào." in source
    action = source.split("def _show_recovery_status(self)", 1)[1].split("def _open_pending_recovery_review", 1)[0]
    assert ".restore(" not in action and ".publish(" not in action
