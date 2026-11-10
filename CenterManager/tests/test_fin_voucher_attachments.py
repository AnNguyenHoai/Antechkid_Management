# -*- coding: utf-8 -*-
"""FEAT-003/FEAT-004: optional accounting vouchers for Income/Expense (D-009)."""
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from centermanager.core.clock import Clock, reset_clock, set_clock
from centermanager.core.current_user import CurrentUserContext
from centermanager.database.base import Base
from centermanager.models import Expense, FinanceAttachment
from centermanager.models.financial_settlement import FinancialSettlement
from centermanager.services.finance_attachment_service import (
    FinanceAttachmentService,
    FinanceAttachmentValidationError,
)
from centermanager.services.permission_service import PermissionDeniedError

ROOT = Path(__file__).resolve().parents[1]
PDF = b"%PDF-1.4\n%voucher\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _user(*permissions):
    return SimpleNamespace(
        id=None, username="voucher-tester", full_name="Voucher Tester",
        is_admin=False, is_active=True, role=SimpleNamespace(name="MANAGER"),
        permissions=set(permissions),
    )


EDITOR = _user("finance.view", "finance.expense.update", "finance.income.update")


@pytest.fixture
def env(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'vouchers.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add(Expense(id=1, category="Other", description="x", amount=100.0, payment_method="CASH",
                            payment_date=date(2026, 9, 10), status="Completed", funding_source="COMPANY"))
        session.add(Expense(id=2, category="Other", description="deleted", amount=50.0, payment_method="CASH",
                            payment_date=date(2026, 9, 10), status="Completed",
                            deleted_at=datetime(2026, 9, 11)))
    runtime = tmp_path / "runtime"
    attachments = runtime / "Attachment"
    attachments.mkdir(parents=True)
    set_clock(Clock(now_fn=lambda: datetime(2026, 10, 20, 9, 0), today_fn=lambda: date(2026, 10, 20)))
    service = FinanceAttachmentService(factory, attachments)
    try:
        yield factory, service, tmp_path, runtime
    finally:
        reset_clock()
        engine.dispose()


def _file(directory: Path, name: str, content: bytes) -> Path:
    path = directory / name
    path.write_bytes(content)
    return path


def test_voucher_is_stored_once_outside_the_database(env):
    _factory, service, tmp_path, runtime = env
    source = _file(tmp_path, "receipt.pdf", PDF)
    with CurrentUserContext(EDITOR):
        attachment = service.add_attachment("EXPENSE", 1, source)

    assert attachment.mime_type == "application/pdf"
    assert attachment.size_bytes == len(PDF)
    assert attachment.stored_path == f"Finance/2026/10/{attachment.sha256}.pdf"
    stored = runtime / "Attachment" / attachment.stored_path
    assert stored.read_bytes() == PDF
    assert service.resolve_path(attachment) == stored
    # SQLite holds metadata only.
    assert not hasattr(FinanceAttachment, "content")


def test_voucher_allowed_in_confirmed_period(env):
    factory, service, tmp_path, _runtime = env
    with factory.begin() as session:
        session.add(FinancialSettlement(
            finance_period_start=date(2026, 9, 1), finance_period_end=date(2026, 9, 30),
            status=FinancialSettlement.STATUS_CONFIRMED,
        ))
    with CurrentUserContext(EDITOR):
        service.add_attachment("EXPENSE", 1, _file(tmp_path, "late.pdf", PDF))
        assert len(service.list_attachments("EXPENSE", 1)) == 1


def test_limits_type_signature_size_and_duplicates(env, monkeypatch):
    _factory, service, tmp_path, _runtime = env
    with CurrentUserContext(EDITOR):
        with pytest.raises(FinanceAttachmentValidationError):
            service.add_attachment("EXPENSE", 1, _file(tmp_path, "notes.docx", PDF))
        with pytest.raises(FinanceAttachmentValidationError):
            service.add_attachment("EXPENSE", 1, _file(tmp_path, "fake.pdf", b"MZ not a pdf"))
        monkeypatch.setattr(FinanceAttachmentService, "MAX_FILE_BYTES", 10)
        with pytest.raises(FinanceAttachmentValidationError):
            service.add_attachment("EXPENSE", 1, _file(tmp_path, "big.pdf", PDF))
        monkeypatch.setattr(FinanceAttachmentService, "MAX_FILE_BYTES", 5 * 1024 * 1024)

        first = service.add_attachment("EXPENSE", 1, _file(tmp_path, "a.pdf", PDF))
        # FIN-04: a repeated upload with the same digest is an idempotent
        # retry, not a second metadata row or a user-visible failure.
        replay = service.add_attachment("EXPENSE", 1, _file(tmp_path, "a-copy.pdf", PDF))
        assert first.id == replay.id
        assert service.count_for("EXPENSE", [1]) == {1: 1}
        for index in range(4):
            service.add_attachment("EXPENSE", 1, _file(tmp_path, f"p{index}.png", PNG + bytes([index])))
        with pytest.raises(FinanceAttachmentValidationError):
            service.add_attachment("EXPENSE", 1, _file(tmp_path, "sixth.pdf", PDF + b"6"))
        assert service.count_for("EXPENSE", [1]) == {1: 5}


def test_deleted_or_missing_record_rejected(env):
    _factory, service, tmp_path, _runtime = env
    with CurrentUserContext(EDITOR):
        for entity_id in (2, 999):
            with pytest.raises(FinanceAttachmentValidationError):
                service.add_attachment("EXPENSE", entity_id, _file(tmp_path, "r.pdf", PDF))


def test_remove_hides_metadata_but_keeps_file(env):
    _factory, service, tmp_path, runtime = env
    with CurrentUserContext(EDITOR):
        attachment = service.add_attachment("EXPENSE", 1, _file(tmp_path, "r.pdf", PDF))
        service.remove_attachment(attachment.id)
        assert service.list_attachments("EXPENSE", 1) == []
        # The same voucher may be attached again after hiding.
        service.add_attachment("EXPENSE", 1, _file(tmp_path, "again.pdf", PDF))
    assert (runtime / "Attachment" / attachment.stored_path).exists()


def test_mutation_requires_record_capability(env):
    _factory, service, tmp_path, _runtime = env
    with CurrentUserContext(_user("finance.view")):
        with pytest.raises(PermissionDeniedError):
            service.add_attachment("EXPENSE", 1, _file(tmp_path, "r.pdf", PDF))


def test_resolve_falls_back_to_pulled_repository_copy(env):
    _factory, service, tmp_path, runtime = env
    with CurrentUserContext(EDITOR):
        attachment = service.add_attachment("EXPENSE", 1, _file(tmp_path, "r.pdf", PDF))
    local = runtime / "Attachment" / attachment.stored_path
    pulled = runtime / "repository" / "Attachments" / attachment.stored_path
    pulled.parent.mkdir(parents=True)
    pulled.write_bytes(local.read_bytes())
    local.unlink()
    assert service.resolve_path(attachment) == pulled


def test_publish_sync_is_incremental_and_never_deletes(tmp_path):
    pytest.importorskip("PySide6")
    from centermanager.platform.synchronization.git_synchronization_provider import GitSynchronizationProvider

    runtime = tmp_path / "runtime"
    provider = GitSynchronizationProvider.__new__(GitSynchronizationProvider)
    provider._repo_path = runtime / "repository"
    provider._repo_path.mkdir(parents=True)
    voucher = runtime / "Attachment" / "Finance" / "2026" / "10" / ("a" * 64 + ".pdf")
    voucher.parent.mkdir(parents=True)
    voucher.write_bytes(PDF)
    other_machine = provider._repo_path / "Attachments" / "Finance" / "2026" / "09" / ("b" * 64 + ".pdf")
    other_machine.parent.mkdir(parents=True)
    other_machine.write_bytes(PDF)

    assert provider._sync_finance_attachments_to_repository() == 1
    assert (provider._repo_path / "Attachments" / "Finance" / "2026" / "10" / voucher.name).read_bytes() == PDF
    assert other_machine.exists()
    assert provider._sync_finance_attachments_to_repository() == 0


def test_voucher_names_match_recovery_immutable_contract():
    """TECH-011 skips content-addressed vouchers in captures by name."""
    from centermanager.platform.write_recovery import _is_immutable_attachment

    name = "c" * 64 + ".jpg"
    assert _is_immutable_attachment("attachments", f"Finance/2026/10/{name}")
    assert _is_immutable_attachment("repository", f"Attachments/Finance/2026/10/{name}")


def test_publish_paths_call_finance_sync():
    source = (ROOT / "src/centermanager/platform/synchronization/git_synchronization_provider.py").read_text(encoding="utf-8")
    assert source.count("self._sync_finance_attachments_to_repository()") == 2


def test_migration_and_schema_verifier_register_table():
    migration = (ROOT / "migrations/versions/1e10a044_finance_attachments.py").read_text(encoding="utf-8")
    verifier = (ROOT / "src/centermanager/database/migration.py").read_text(encoding="utf-8")
    assert 'down_revision = "1e10a043"' in migration
    assert "LargeBinary" not in migration and "BLOB" not in migration
    assert '"finance_attachments": {' in verifier


class _FakeVoucherService:
    MAX_FILES_PER_RECORD = 5

    def __init__(self):
        self.added = []

    def list_attachments(self, entity_type, entity_id):
        return []

    @staticmethod
    def inspect_file(path):
        if not str(path).endswith(".pdf"):
            raise ValueError("Chỉ chấp nhận chứng từ PDF, PNG hoặc JPG.")
        return {}

    def add_attachment(self, entity_type, entity_id, path, original_filename=None):
        self.added.append((entity_type, entity_id, original_filename))


def test_widget_keeps_new_record_vouchers_pending_until_saved(qtbot, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from centermanager.ui.finance_workspace.voucher_attachment_widget import VoucherAttachmentWidget

    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: None)
    service = _FakeVoucherService()
    widget = VoucherAttachmentWidget(service, "EXPENSE", None)
    qtbot.addWidget(widget)
    files = [str(_file(tmp_path, f"r{i}.pdf", PDF)) for i in range(6)]
    errors = widget.add_files(files + [str(_file(tmp_path, "x.docx", PDF))])

    assert widget.list_widget.count() == 5
    assert len(errors) == 2
    assert not widget.add_btn.isEnabled()
    assert service.added == []
    assert widget.commit_pending(42) == []
    assert [entry[1] for entry in service.added] == [42] * 5


def test_forms_and_lists_offer_vouchers_only_with_service():
    expense_form = (ROOT / "src/centermanager/ui/finance_workspace/expense_form_dialog.py").read_text(encoding="utf-8")
    income_form = (ROOT / "src/centermanager/ui/finance_workspace/income_form_dialog.py").read_text(encoding="utf-8")
    for source in (expense_form, income_form):
        assert "if self._attachment_service is not None:" in source
        assert "self._commit_vouchers(" in source
    for page in ("expense_list_page.py", "income_list_page.py"):
        source = (ROOT / "src/centermanager/ui/finance_workspace" / page).read_text(encoding="utf-8")
        assert 'menu.addAction("Chứng từ…"' in source
        assert "domain_allowed=True" in source
