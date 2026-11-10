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


def test_voucher_batch_lookup_excludes_deleted_and_other_types():
    from datetime import datetime
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from centermanager.models.finance_attachment import FinanceAttachment
    from centermanager.repositories.finance_attachment_repository import FinanceAttachmentRepository

    engine = create_engine("sqlite:///:memory:")
    FinanceAttachment.__table__.create(bind=engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    def row(kind, entity_id, name, deleted=False):
        return FinanceAttachment(
            entity_type=kind, entity_id=entity_id, original_filename=name,
            stored_path="Finance/2026/11/" + "f" * 64 + ".pdf",
            mime_type="application/pdf", size_bytes=12,
            sha256="f" * 64, uploaded_at=datetime(2026, 11, 10),
            deleted_at=datetime(2026, 11, 11) if deleted else None,
        )
    with factory.begin() as session:
        session.add_all([
            row("INCOME", 11, "invoice.pdf"),
            row("INCOME", 11, "hidden.pdf", deleted=True),
            row("EXPENSE", 11, "wrong-kind.pdf"),
            row("INCOME", 12, "second.pdf"),
        ])
    with factory() as session:
        repo = FinanceAttachmentRepository(session)
        matches = repo.list_active_for("INCOME", [11, 12, 999])
        assert sorted(matches) == [11, 12]
        assert [item.original_filename for item in matches[11]] == ["invoice.pdf"]
        assert [item.original_filename for item in matches[12]] == ["second.pdf"]
        assert repo.list_active_for("INCOME", []) == {}
    engine.dispose()


def test_recovery_status_action_shows_empty_information_dialog(monkeypatch):
    from centermanager.ui.main_window import MainWindow
    from centermanager.platform import recovery_case_registry, recovery_review_notices, write_recovery
    from PySide6.QtWidgets import QMessageBox

    prompts = []
    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", lambda: object())
    monkeypatch.setattr(
        recovery_review_notices, "RecoveryReviewNotices",
        lambda _journal: SimpleNamespace(pending=lambda: []),
    )
    monkeypatch.setattr(
        recovery_case_registry, "RecoveryCaseRegistry",
        lambda _journal: SimpleNamespace(list_cases=lambda: []),
    )
    monkeypatch.setattr(
        QMessageBox, "information",
        lambda *_args: prompts.append(_args[2]) if len(_args) > 2 else None,
    )
    fake_window = SimpleNamespace(_manual_review_archives=lambda: [])
    MainWindow._show_recovery_status(fake_window)
    assert prompts == ["Không có Recovery nào cần kiểm tra."]
