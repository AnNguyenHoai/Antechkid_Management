"""P1 regression: finance vouchers and complete SQLCipher table capability inventory.

A missing SQLite authorizer table mapping fails at the DBAPI boundary even
when the relevant business service allows the operation. Preserve the
unknown-table fail-closed policy and do not grant finance.view a write permit.
"""
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import insert, update

import centermanager.models  # noqa: F401 -- register all ORM tables
from centermanager.database.base import Base
from centermanager.database.mutation_permissions import mutation_permissions
from centermanager.database.mutation_authority import MutationAuthorityError
from centermanager.core.current_user import CurrentUserContext
from centermanager.models.expense import Expense
from centermanager.models.finance_attachment import FinanceAttachment
from centermanager.services.finance_attachment_service import FinanceAttachmentService
from centermanager.services.permission_service import PermissionDeniedError
from tests.test_e1b2a_post_publish_consistency import reporting, remote_rows  # noqa: F401


def test_every_registered_orm_table_has_a_explicit_mutation_capability_floor():
    """New models must not silently become unwritable in production."""
    missing = sorted(
        table for table in Base.metadata.tables
        if not mutation_permissions(table, 18)
        or not mutation_permissions(table, 23)
        or not mutation_permissions(table, 9)
    )
    assert missing == [], f"Missing SQLCipher DML capability maps: {missing}"
    assert mutation_permissions("totally_unknown_table", 18) == ()


@pytest.mark.parametrize("action", [18, 23, 9])
def test_finance_vouchers_admit_only_finance_write_capabilities(action):
    accepted = set(mutation_permissions("finance_attachments", action))
    assert accepted == {
        "finance.income.create", "finance.income.update",
        "finance.expense.create", "finance.expense.update",
    }
    assert "finance.view" not in accepted


def _principal(permissions):
    return SimpleNamespace(
        id=1, username="synthetic", role=SimpleNamespace(name="finance"),
        is_active=True, permissions=set(permissions),
    )


def test_expense_voucher_upload_and_remove_under_real_sqlcipher_write(reporting, tmp_path):
    w = reporting
    assert w.tx.start_editing(), w.tx.last_start_error
    with w.factory() as db:
        db.add(Expense(
            id=1, category="Office", description="Synthetic expense",
            amount=12000.0, payment_method="Cash",
            payment_date=date(2026, 11, 9), status="Completed",
        ))
        db.commit()

    voucher_file = tmp_path / "receipt.jpg"
    voucher_file.write_bytes(b"\xff\xd8\xff\xe0synthetic-jpeg-fixture")
    service = FinanceAttachmentService(w.factory, tmp_path / "runtime-vouchers")
    with CurrentUserContext(_principal({"finance.expense.create"})):
        attachment = service.add_attachment("EXPENSE", 1, voucher_file)
        assert attachment.id > 0
        assert service.resolve_path(attachment).is_file()
        service.remove_attachment(attachment.id)
        with w.factory() as db:
            assert db.get(FinanceAttachment, attachment.id).deleted_at is not None
        w.tx.mark_dirty()
        assert w.tx.finish_editing()

    remote = remote_rows(
        w, "SELECT original_filename, deleted_at FROM finance_attachments WHERE entity_id=1"
    )
    assert remote and remote[0][0] == "receipt.jpg"
    assert remote[0][1] is not None


def test_finance_view_and_unrelated_role_cannot_write_vouchers(reporting):
    w = reporting
    assert w.tx.start_editing(), w.tx.last_start_error
    values = dict(
        entity_type="EXPENSE", entity_id=1, original_filename="blocked.jpg",
        stored_path="Finance/2026/11/blocked.jpg", mime_type="image/jpeg",
        size_bytes=5, sha256="a" * 64, uploaded_at=datetime(2026, 11, 9),
    )
    for permissions in ({"finance.view"}, {"student.update"}, set()):
        with CurrentUserContext(_principal(permissions)), w.factory() as db:
            with pytest.raises(MutationAuthorityError, match="capability"):
                db.execute(insert(FinanceAttachment).values(**values))
            db.rollback()
    assert remote_rows(w, "SELECT count(*) FROM finance_attachments") == [(0,)]


def test_voucher_insert_requires_write_even_with_finance_capability(reporting):
    w = reporting
    with CurrentUserContext(_principal({"finance.expense.create"})), w.factory() as db:
        with pytest.raises(MutationAuthorityError, match="WRITE"):
            db.execute(insert(FinanceAttachment).values(
                entity_type="EXPENSE", entity_id=1,
                original_filename="blocked.jpg", stored_path="Finance/blocked.jpg",
                mime_type="image/jpeg", size_bytes=5, sha256="a" * 64,
                uploaded_at=datetime(2026, 11, 9),
            ))
        db.rollback()


def test_service_requires_target_specific_finance_write_capability(reporting, tmp_path):
    w = reporting
    service = FinanceAttachmentService(w.factory, tmp_path / "vouchers")
    # A finance.income capability does not authorize attaching to an Expense,
    # even though both entity types share the SQLCipher metadata table.
    with CurrentUserContext(_principal({"finance.income.create"})):
        with pytest.raises(PermissionDeniedError):
            service._require_mutation("EXPENSE")
        service._require_mutation("INCOME")
    with CurrentUserContext(_principal({"finance.expense.update"})):
        service._require_mutation("EXPENSE")
        with pytest.raises(PermissionDeniedError):
            service._require_mutation("INCOME")
