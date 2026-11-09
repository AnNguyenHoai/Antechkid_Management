# -*- coding: utf-8 -*-
"""Accounting vouchers attached to Income/Expense (FEAT-003, PO decision D-009).

* Optional; PDF/PNG/JPG only; at most 5 MB per file and 5 files per record.
* Allowed in closed (settled) periods: a voucher never changes an amount.
* Files are immutable and content-addressed under the runtime attachment
  tree: ``Finance/<yyyy>/<mm>/<sha256>.<ext>``. SQLite stores metadata only.
* Kept forever: removing a voucher hides its metadata; the file stays.
"""
from __future__ import annotations

import hashlib
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from centermanager.services.recovery_change_outbox import record_for_active_write, mirror_after_successful_commit
from centermanager.core.clock import get_clock
from centermanager.core.current_user import get_current_user
from centermanager.core.permission_guard import require_any_permission, require_permission
from centermanager.models.finance_attachment import FinanceAttachment
from centermanager.repositories.provider import RepositoryProvider, create_default_repository_provider
from centermanager.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class FinanceAttachmentError(Exception):
    pass


class FinanceAttachmentValidationError(FinanceAttachmentError):
    pass


class FinanceAttachmentService:
    MAX_FILE_BYTES = 5 * 1024 * 1024
    MAX_FILES_PER_RECORD = 5
    ALLOWED_TYPES = {
        ".pdf": ("application/pdf", "pdf"),
        ".png": ("image/png", "png"),
        ".jpg": ("image/jpeg", "jpg"),
        ".jpeg": ("image/jpeg", "jpg"),
    }
    _SIGNATURES = {
        "application/pdf": (b"%PDF-",),
        "image/png": (b"\x89PNG\r\n\x1a\n",),
        "image/jpeg": (b"\xff\xd8\xff",),
    }
    _MUTATION_CAPABILITIES = {
        FinanceAttachment.ENTITY_INCOME: ["finance.income.create", "finance.income.update"],
        FinanceAttachment.ENTITY_EXPENSE: ["finance.expense.create", "finance.expense.update"],
    }

    def __init__(
        self,
        session_factory: Any,
        attachments_root: Path,
        repository_provider: Optional[RepositoryProvider] = None,
        audit_service: Optional[AuditService] = None,
        event_bus=None,
    ) -> None:
        self._session_factory = session_factory
        self._attachments_root = Path(attachments_root)
        self._repository_provider = repository_provider or create_default_repository_provider()
        self._audit_service = audit_service or AuditService(
            session_factory, repository_provider=self._repository_provider
        )
        self._event_bus = event_bus

    def set_event_bus(self, event_bus) -> None:
        self._event_bus = event_bus

    # ---- paths -------------------------------------------------------------

    @property
    def repository_root(self) -> Path:
        """Repository mirror of the runtime attachment tree (plural ``Attachments``)."""
        return self._attachments_root.parent / "repository" / "Attachments"

    def resolve_path(self, attachment: FinanceAttachment) -> Path:
        """Local file for viewing; falls back to the pulled repository copy."""
        relative = Path(attachment.stored_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise FinanceAttachmentError("Invalid voucher path.")
        runtime = self._attachments_root / relative
        if runtime.is_file():
            return runtime
        repository = self.repository_root / relative
        if repository.is_file():
            return repository
        raise FinanceAttachmentError(
            "Không tìm thấy file chứng từ trên máy này. Hãy đồng bộ dữ liệu rồi thử lại."
        )

    # ---- validation --------------------------------------------------------

    @classmethod
    def _validate_entity_type(cls, entity_type: str) -> str:
        if entity_type not in cls._MUTATION_CAPABILITIES:
            raise FinanceAttachmentValidationError(f"Unsupported voucher target: {entity_type}")
        return entity_type

    def _require_mutation(self, entity_type: str) -> None:
        @require_any_permission(self._MUTATION_CAPABILITIES[entity_type])
        def _check(_self):
            return None
        _check(self)

    @classmethod
    def inspect_file(cls, source_path) -> Dict[str, Any]:
        """Validate a candidate file and return its type, size and SHA-256."""
        source = Path(source_path)
        if not source.is_file():
            raise FinanceAttachmentValidationError(f"Không tìm thấy file: {source}")
        suffix = source.suffix.lower()
        if suffix not in cls.ALLOWED_TYPES:
            raise FinanceAttachmentValidationError("Chỉ chấp nhận chứng từ PDF, PNG hoặc JPG.")
        mime, extension = cls.ALLOWED_TYPES[suffix]
        size = source.stat().st_size
        if size <= 0:
            raise FinanceAttachmentValidationError("File chứng từ rỗng.")
        if size > cls.MAX_FILE_BYTES:
            raise FinanceAttachmentValidationError("Mỗi chứng từ tối đa 5 MB.")
        digest = hashlib.sha256()
        with source.open("rb") as stream:
            head = stream.read(16)
            digest.update(head)
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        if not any(head.startswith(signature) for signature in cls._SIGNATURES[mime]):
            raise FinanceAttachmentValidationError(
                "Nội dung file không khớp định dạng PDF/PNG/JPG."
            )
        return {"mime_type": mime, "extension": extension, "size_bytes": size, "sha256": digest.hexdigest()}

    # ---- storage -----------------------------------------------------------

    def _store_file(self, source: Path, sha256: str, extension: str) -> str:
        today = get_clock().today()
        relative = Path("Finance") / f"{today:%Y}" / f"{today:%m}" / f"{sha256}.{extension}"
        target = self._attachments_root / relative
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            handle, temporary = tempfile.mkstemp(prefix=".voucher_", dir=target.parent)
            os.close(handle)
            try:
                shutil.copyfile(source, temporary)
                os.replace(temporary, target)
            except Exception:
                Path(temporary).unlink(missing_ok=True)
                raise
        return relative.as_posix()

    def _entity_exists(self, session, entity_type: str, entity_id: int) -> bool:
        if entity_type == FinanceAttachment.ENTITY_INCOME:
            return self._repository_provider.incomes(session).get_by_id(entity_id) is not None
        return self._repository_provider.expenses(session).get_by_id(entity_id) is not None

    def _publish(self, action: str, attachment_id: int) -> None:
        if self._event_bus is None:
            return
        try:
            from centermanager.events.finance_events import FinanceDataChanged
            self._event_bus.publish(
                FinanceDataChanged(entity="finance_attachment", action=action, entity_id=attachment_id)
            )
        except Exception:
            logger.exception("Voucher %s committed but FinanceDataChanged publish failed", attachment_id)

    # ---- commands ----------------------------------------------------------

    def add_attachment(
        self,
        entity_type: str,
        entity_id: int,
        source_path,
        original_filename: Optional[str] = None,
    ) -> FinanceAttachment:
        entity_type = self._validate_entity_type(entity_type)
        self._require_mutation(entity_type)
        info = self.inspect_file(source_path)
        name = (original_filename or Path(source_path).name).strip()[:255] or f"voucher.{info['extension']}"
        with self._session_factory() as session:
            if not self._entity_exists(session, entity_type, entity_id):
                raise FinanceAttachmentValidationError("Khoản thu/chi không tồn tại hoặc đã bị xóa.")
            repo = self._repository_provider.finance_attachments(session)
            # FIN-04: if the previous upload committed but UI lost its
            # acknowledgement, return the exact existing voucher instead of
            # creating duplicate metadata. Ensure runtime content is staged
            # for the next Git publication before claiming retry success.
            existing = repo.find_active_sha(entity_type, entity_id, info["sha256"])
            if existing is not None:
                # Do not silently recreate a missing Git artifact. Such a
                # repair needs its own authorized WRITE publication, otherwise
                # a DB-identical retry could be considered 'clean' and omit
                # the file from MAIN. Keep the voucher pending for explicit
                # recovery instead of returning false success.
                try:
                    self.resolve_path(existing)
                except FinanceAttachmentError as exc:
                    raise FinanceAttachmentValidationError(
                        "Previously attached voucher content is missing; "
                        "synchronize/recover the repository before retrying"
                    ) from exc
                return existing
            if repo.count_active(entity_type, entity_id) >= self.MAX_FILES_PER_RECORD:
                raise FinanceAttachmentValidationError("Mỗi khoản tối đa 5 chứng từ.")
            stored_path = self._store_file(Path(source_path), info["sha256"], info["extension"])
            user = get_current_user()
            attachment = FinanceAttachment(
                entity_type=entity_type,
                entity_id=entity_id,
                original_filename=name,
                stored_path=stored_path,
                mime_type=info["mime_type"],
                size_bytes=info["size_bytes"],
                sha256=info["sha256"],
                uploaded_by=getattr(user, "username", None),
                uploaded_at=get_clock().now(),
            )
            repo.add(attachment)
            repo.flush()
            self._audit_service.record_in_session(
                session,
                action="ATTACH_VOUCHER",
                module="finance",
                target_type=entity_type.lower(),
                target_id=entity_id,
                target_name=name,
                details={"attachment_id": attachment.id, "sha256": info["sha256"],
                         "size_bytes": info["size_bytes"], "stored_path": stored_path},
                actor=user,
                entity_type="FinanceAttachment",
                entity_id=attachment.id,
                summary=f"ATTACH_VOUCHER: {entity_type}#{entity_id}",
            )
            record_for_active_write(
                session, module="attachment", action="ATTACH",
                entity_type="FinanceAttachment", entity_id=attachment.id,
                entity_object=attachment, summary_args={"attachment_id": attachment.id},
            )
            session.commit()
            mirror_after_successful_commit(session)
            repo.refresh(attachment)
        self._publish("created", attachment.id)
        return attachment

    def remove_attachment(self, attachment_id: int) -> None:
        """Hide a voucher (metadata soft delete). The file is kept forever."""
        with self._session_factory() as session:
            repo = self._repository_provider.finance_attachments(session)
            attachment = repo.get_by_id(attachment_id)
            if attachment is None:
                raise FinanceAttachmentValidationError("Chứng từ không tồn tại hoặc đã bị ẩn.")
            self._require_mutation(attachment.entity_type)
            repo.soft_delete(attachment, get_clock().now())
            self._audit_service.record_in_session(
                session,
                action="REMOVE_VOUCHER",
                module="finance",
                target_type=attachment.entity_type.lower(),
                target_id=attachment.entity_id,
                target_name=attachment.original_filename,
                details={"attachment_id": attachment.id, "sha256": attachment.sha256},
                actor=get_current_user(),
                entity_type="FinanceAttachment",
                entity_id=attachment.id,
                summary=f"REMOVE_VOUCHER: {attachment.entity_type}#{attachment.entity_id}",
            )
            record_for_active_write(
                session, module="attachment", action="REMOVE",
                entity_type="FinanceAttachment", entity_id=attachment.id,
                entity_object=attachment, summary_args={"attachment_id": attachment.id},
            )
            session.commit()
            mirror_after_successful_commit(session)
        self._publish("deleted", attachment_id)

    # ---- queries -----------------------------------------------------------

    @require_permission("finance.view")
    def list_attachments(self, entity_type: str, entity_id: int) -> List[FinanceAttachment]:
        entity_type = self._validate_entity_type(entity_type)
        with self._session_factory() as session:
            return self._repository_provider.finance_attachments(session).list_active(entity_type, entity_id)

    @require_permission("finance.view")
    def count_for(self, entity_type: str, entity_ids: Iterable[int]) -> Dict[int, int]:
        entity_type = self._validate_entity_type(entity_type)
        with self._session_factory() as session:
            return self._repository_provider.finance_attachments(session).count_active_for(entity_type, entity_ids)
