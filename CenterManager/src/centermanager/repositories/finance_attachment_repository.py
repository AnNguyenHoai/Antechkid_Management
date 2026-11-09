# -*- coding: utf-8 -*-
"""Persistence for finance voucher metadata (FEAT-003)."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from centermanager.models.finance_attachment import FinanceAttachment


class FinanceAttachmentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, attachment: FinanceAttachment) -> FinanceAttachment:
        self._session.add(attachment)
        return attachment

    def flush(self) -> None:
        self._session.flush()

    def refresh(self, attachment: FinanceAttachment) -> FinanceAttachment:
        self._session.refresh(attachment)
        return attachment

    def get_by_id(self, attachment_id: int) -> Optional[FinanceAttachment]:
        return (
            self._session.query(FinanceAttachment)
            .filter(FinanceAttachment.id == attachment_id, FinanceAttachment.deleted_at.is_(None))
            .first()
        )

    def _active(self, entity_type: str, entity_id: int):
        return self._session.query(FinanceAttachment).filter(
            FinanceAttachment.entity_type == entity_type,
            FinanceAttachment.entity_id == entity_id,
            FinanceAttachment.deleted_at.is_(None),
        )

    def list_active(self, entity_type: str, entity_id: int) -> List[FinanceAttachment]:
        return self._active(entity_type, entity_id).order_by(FinanceAttachment.uploaded_at, FinanceAttachment.id).all()

    def count_active(self, entity_type: str, entity_id: int) -> int:
        return self._active(entity_type, entity_id).count()

    def find_active_sha(self, entity_type: str, entity_id: int, sha256: str) -> Optional[FinanceAttachment]:
        return self._active(entity_type, entity_id).filter(
            FinanceAttachment.sha256 == sha256
        ).first()

    def exists_active_sha(self, entity_type: str, entity_id: int, sha256: str) -> bool:
        return self.find_active_sha(entity_type, entity_id, sha256) is not None

    def count_active_for(self, entity_type: str, entity_ids: Iterable[int]) -> Dict[int, int]:
        ids = list({int(i) for i in entity_ids})
        if not ids:
            return {}
        rows = (
            self._session.query(FinanceAttachment.entity_id, func.count(FinanceAttachment.id))
            .filter(
                FinanceAttachment.entity_type == entity_type,
                FinanceAttachment.entity_id.in_(ids),
                FinanceAttachment.deleted_at.is_(None),
            )
            .group_by(FinanceAttachment.entity_id)
            .all()
        )
        return {int(entity_id): int(count) for entity_id, count in rows}

    def soft_delete(self, attachment: FinanceAttachment, when: datetime) -> None:
        attachment.deleted_at = when
