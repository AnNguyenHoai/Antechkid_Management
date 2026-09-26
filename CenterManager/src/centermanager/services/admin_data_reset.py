# -*- coding: utf-8 -*-
"""Admin-only workspace data reset orchestration.

Destructive persistence stays in the repository. This service owns authorization,
WRITE-mode enforcement, typed confirmation, safety backup, transaction and audit.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import sessionmaker

from centermanager.core.current_user import get_current_user
from centermanager.platform.backup.backup_service import BackupService
from centermanager.repositories.admin_data_reset_repository import ResetPreviewData
from centermanager.repositories.provider import (
    RepositoryProvider,
    create_default_repository_provider,
)
from centermanager.services.audit_service import AuditService


class AdminDataResetError(RuntimeError):
    pass


class AdminDataResetAuthorizationError(AdminDataResetError):
    pass


class AdminDataResetValidationError(AdminDataResetError):
    pass


@dataclass(frozen=True)
class AdminDataResetPreview:
    scope: str
    include_finance: bool
    confirmation_phrase: str
    tables: tuple[str, ...]
    counts: dict[str, int]
    blockers: dict[str, int]
    finance_counts: dict[str, int]

    @property
    def total_rows(self) -> int:
        return sum(self.counts.values())

    @property
    def can_reset(self) -> bool:
        return not self.blockers


@dataclass(frozen=True)
class AdminDataResetResult:
    scope: str
    deleted_counts: dict[str, int]
    backup_path: str

    @property
    def deleted_rows(self) -> int:
        return sum(self.deleted_counts.values())


class AdminDataResetService:
    VALID_SCOPES = (
        "student",
        "class",
        "teacher",
        "employee",
        "finance",
        "operational",
        "all_business",
    )

    def __init__(
        self,
        session_factory: sessionmaker,
        collaboration_manager=None,
        backup_service: Optional[BackupService] = None,
        audit_service: Optional[AuditService] = None,
        repository_provider: Optional[RepositoryProvider] = None,
    ) -> None:
        self._session_factory = session_factory
        self._collaboration_manager = collaboration_manager
        self._backup_service = backup_service or BackupService()
        self._repository_provider = (
            repository_provider or create_default_repository_provider()
        )
        self._audit_service = audit_service or AuditService(
            session_factory, repository_provider=self._repository_provider
        )

    @staticmethod
    def _normalize_scope(scope: str) -> str:
        value = str(scope or "").strip().lower()
        if value not in AdminDataResetService.VALID_SCOPES:
            raise AdminDataResetValidationError(f"Unsupported reset scope: {scope}")
        return value

    @staticmethod
    def confirmation_phrase(scope: str) -> str:
        return f"RESET {AdminDataResetService._normalize_scope(scope).upper()}"

    @staticmethod
    def _require_admin():
        actor = get_current_user()
        if actor is None or not bool(getattr(actor, "is_admin", False)):
            raise AdminDataResetAuthorizationError("Administrator access is required.")
        return actor

    def _require_write(self) -> None:
        manager = self._collaboration_manager
        try:
            writable = bool(
                manager is not None
                and manager.is_initialized()
                and manager.is_writing()
            )
        except Exception:
            writable = False
        if not writable:
            raise AdminDataResetAuthorizationError(
                "WRITE mode is required before resetting workspace data."
            )

    @staticmethod
    def _preview_from_data(
        scope: str, include_finance: bool, data: ResetPreviewData
    ) -> AdminDataResetPreview:
        return AdminDataResetPreview(
            scope=scope,
            include_finance=include_finance,
            confirmation_phrase=AdminDataResetService.confirmation_phrase(scope),
            tables=data.tables,
            counts=data.counts,
            blockers=data.blockers,
            finance_counts=data.finance_counts,
        )

    def preview(self, scope: str, *, include_finance: bool = False) -> AdminDataResetPreview:
        self._require_admin()
        normalized = self._normalize_scope(scope)
        with self._session_factory() as session:
            data = self._repository_provider.admin_data_resets(session).preview(
                normalized, include_finance=include_finance
            )
            return self._preview_from_data(normalized, include_finance, data)

    def reset(
        self,
        scope: str,
        *,
        include_finance: bool = False,
        reason: str,
        confirmation: str,
    ) -> AdminDataResetResult:
        actor = self._require_admin()
        self._require_write()
        normalized = self._normalize_scope(scope)
        clean_reason = str(reason or "").strip()
        if not clean_reason:
            raise AdminDataResetValidationError("A reset reason is required.")
        expected = self.confirmation_phrase(normalized)
        if str(confirmation or "").strip() != expected:
            raise AdminDataResetValidationError(
                f'Type "{expected}" to confirm this destructive operation.'
            )

        with self._session_factory() as session:
            preview_data = self._repository_provider.admin_data_resets(session).preview(
                normalized, include_finance=include_finance
            )
        if preview_data.blockers:
            blocker_text = ", ".join(
                f"{name}={count}" for name, count in sorted(preview_data.blockers.items())
            )
            raise AdminDataResetValidationError(
                "Reset is blocked by retained dependent data: " + blocker_text
            )

        backup = self._backup_service.create_backup(
            label=f"pre_data_reset_{normalized}"
        )
        if not backup.success or backup.backup_path is None:
            raise AdminDataResetError(
                f"Safety backup failed; no data was deleted: "
                f"{backup.error or 'unknown error'}"
            )

        with self._session_factory() as session:
            repository = self._repository_provider.admin_data_resets(session)
            current = repository.preview(normalized, include_finance=include_finance)
            if current.blockers:
                raise AdminDataResetValidationError(
                    "Reset dependencies changed after preview; retry the operation."
                )
            deleted = repository.delete_tables(current.tables)
            self._audit_service.record_in_session(
                session,
                "ADMIN_DATA_RESET",
                "admin",
                target_type="workspace_data",
                target_id=normalized,
                target_name=normalized,
                actor=actor,
                details={
                    "scope": normalized,
                    "include_finance": bool(include_finance),
                    "reason": clean_reason,
                    "deleted_counts": deleted,
                    "safety_backup": str(backup.backup_path),
                },
                summary=f"Admin reset {normalized} data",
            )
            session.commit()

        return AdminDataResetResult(
            scope=normalized,
            deleted_counts=deleted,
            backup_path=str(backup.backup_path),
        )
