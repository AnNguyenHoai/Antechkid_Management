# -*- coding: utf-8 -*-
"""Fail-closed authorization context for destructive backup restore.

The platform backup layer must never accept an unguarded restore call. Application
orchestration issues this context only after validating the authenticated admin,
WRITE ownership, reason and typed confirmation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_AUTHORITY = object()


@dataclass(frozen=True)
class RestoreAuthorization:
    actor_id: object
    actor_name: str
    reason: str
    confirmation: str
    _authority: object


def issue_restore_authorization(*, actor: Any, reason: str, confirmation: str) -> RestoreAuthorization:
    clean_reason = str(reason or "").strip()
    clean_confirmation = str(confirmation or "").strip()
    if actor is None or not bool(getattr(actor, "is_admin", False)):
        raise PermissionError("Administrator authorization is required for restore.")
    if not clean_reason:
        raise ValueError("Restore reason is required.")
    if not clean_confirmation:
        raise ValueError("Restore confirmation is required.")
    return RestoreAuthorization(
        actor_id=getattr(actor, "id", None),
        actor_name=str(getattr(actor, "username", "") or ""),
        reason=clean_reason,
        confirmation=clean_confirmation,
        _authority=_AUTHORITY,
    )


def validate_restore_authorization(value: object) -> RestoreAuthorization:
    if not isinstance(value, RestoreAuthorization) or value._authority is not _AUTHORITY:
        raise PermissionError(
            "Backup restore requires a validated destructive-operation authorization context."
        )
    if not value.reason or not value.confirmation:
        raise PermissionError("Backup restore authorization context is incomplete.")
    return value
