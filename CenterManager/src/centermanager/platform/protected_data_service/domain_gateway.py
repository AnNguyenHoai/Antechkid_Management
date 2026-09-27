# -*- coding: utf-8 -*-
"""Authenticated application/domain gateway owned by AnTechKidsData."""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping

from sqlalchemy.orm import sessionmaker

from centermanager.core.capabilities import Capability
from centermanager.database.engine import create_engine_for_path
from centermanager.database.encryption import DatabaseKeyStore
from centermanager.repositories.user_repository import UserRepository
from centermanager.security.protected_storage import ProtectedStorageLayout
from centermanager.services.authorization_service import AuthorizationService
from centermanager.services.permission_service import PermissionService, AuthenticationError
from centermanager.services.student_service import StudentService
from centermanager.services.timeline_service import TimelineService


class ProtectedDomainError(RuntimeError):
    pass


class ProtectedDomainAuthenticationError(ProtectedDomainError):
    pass


class ProtectedDomainAuthorizationError(ProtectedDomainError):
    pass


@dataclass(frozen=True)
class ServiceSession:
    token: str
    user_id: int
    caller_sid: str
    expires_at_monotonic: float


class ServiceSessionRegistry:
    """Short-lived bearer capabilities bound to the authenticated Windows SID."""

    def __init__(self, *, ttl_seconds: int = 8 * 60 * 60) -> None:
        self._ttl_seconds = int(ttl_seconds)
        self._sessions: dict[str, ServiceSession] = {}

    def issue(self, user_id: int, caller_sid: str) -> ServiceSession:
        self.prune()
        token = secrets.token_urlsafe(32)
        value = ServiceSession(
            token=token,
            user_id=int(user_id),
            caller_sid=str(caller_sid),
            expires_at_monotonic=time.monotonic() + self._ttl_seconds,
        )
        self._sessions[token] = value
        return value

    def require(self, token: str, caller_sid: str) -> ServiceSession:
        self.prune()
        value = self._sessions.get(str(token or ""))
        if value is None or not secrets.compare_digest(value.caller_sid, str(caller_sid or "")):
            raise ProtectedDomainAuthenticationError("Application session is invalid or expired.")
        return value

    def revoke(self, token: str, caller_sid: str) -> None:
        value = self.require(token, caller_sid)
        self._sessions.pop(value.token, None)

    def prune(self) -> None:
        now = time.monotonic()
        for token in [
            token for token, value in self._sessions.items()
            if value.expires_at_monotonic <= now
        ]:
            self._sessions.pop(token, None)


class ProtectedDomainGateway:
    """Own service-side DB sessions and canonical application authorization.

    DB/key initialization is lazy so the Windows service can install/start and
    answer health checks before protected storage has been staged. First auth or
    domain access fails closed if protected key/database material is unavailable.
    """

    def __init__(
        self,
        layout: ProtectedStorageLayout,
        *,
        session_registry: ServiceSessionRegistry | None = None,
        session_factory=None,
    ) -> None:
        self._layout = layout
        self._sessions = session_registry or ServiceSessionRegistry()
        self._session_factory = session_factory
        self._permission_service = None
        self._timeline_service = None
        self._student_service = None

    def _ensure_services(self):
        if self._session_factory is None:
            key = DatabaseKeyStore(
                bundle_path=self._layout.key_bundle_path,
                machine_scope=True,
            ).load()
            engine = create_engine_for_path(
                self._layout.database_path,
                allow_create=False,
                encrypted=True,
                encryption_key=key,
            )
            self._session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        if self._permission_service is None:
            self._permission_service = PermissionService(self._session_factory)
        if self._timeline_service is None:
            self._timeline_service = TimelineService(self._session_factory)
        if self._student_service is None:
            self._student_service = StudentService(
                self._session_factory,
                timeline_service=self._timeline_service,
            )
        return self._session_factory, self._permission_service, self._student_service

    @staticmethod
    def _principal_summary(user) -> dict[str, Any]:
        return {
            "user_id": int(user.id),
            "username": str(user.username),
            "full_name": str(user.full_name),
            "role": getattr(getattr(user, "role", None), "name", None),
            "permissions": sorted(str(value) for value in getattr(user, "permissions", set())),
            "force_password_change": bool(getattr(user, "force_password_change", False)),
        }

    def authenticate(self, username: str, password: str, caller_sid: str) -> dict[str, Any]:
        _, permission_service, _ = self._ensure_services()
        if not str(username or "").strip() or not password or not caller_sid:
            raise ProtectedDomainAuthenticationError("Invalid username or password.")
        try:
            user = permission_service.authenticate_user(str(username).strip(), str(password))
        except AuthenticationError as exc:
            raise ProtectedDomainAuthenticationError(str(exc)) from exc
        issued = self._sessions.issue(user.id, caller_sid)
        result = self._principal_summary(user)
        result["session_token"] = issued.token
        return result

    def logout(self, token: str, caller_sid: str) -> dict[str, Any]:
        self._sessions.revoke(token, caller_sid)
        return {"logged_out": True}

    def _authorized_user(self, token: str, caller_sid: str, *capabilities: Capability):
        session_factory, _, _ = self._ensure_services()
        service_session = self._sessions.require(token, caller_sid)
        with session_factory() as db:
            user = UserRepository(db).get_by_id_with_role(service_session.user_id)
            if user is None or not user.is_active or user.is_locked:
                self._sessions.revoke(token, caller_sid)
                raise ProtectedDomainAuthenticationError("Application session is no longer valid.")
            if capabilities and not AuthorizationService.allows_any(user, capabilities):
                raise ProtectedDomainAuthorizationError("Required capability is not granted.")
            return user

    def change_password(
        self,
        token: str,
        caller_sid: str,
        current_password: str,
        new_password: str,
    ) -> dict[str, Any]:
        _, permission_service, _ = self._ensure_services()
        user = self._authorized_user(token, caller_sid)
        try:
            updated = permission_service.change_password(
                int(user.id), str(current_password), str(new_password)
            )
        except AuthenticationError as exc:
            raise ProtectedDomainAuthenticationError(str(exc)) from exc
        return {"user": self._principal_summary(updated)}

    @staticmethod
    def _student_dto(student) -> dict[str, Any]:
        return {
            "id": int(student.id),
            "student_code": str(student.student_code),
            "full_name": str(student.full_name),
            "preferred_name": student.preferred_name,
            "date_of_birth": student.date_of_birth.isoformat() if student.date_of_birth else None,
            "gender": student.gender,
            "status": student.status,
            "current_level": student.current_level,
            "enrollment_date": student.enrollment_date.isoformat() if student.enrollment_date else None,
            "notes": student.notes,
        }

    def list_students(self, token: str, caller_sid: str) -> dict[str, Any]:
        _, _, student_service = self._ensure_services()
        self._authorized_user(
            token, caller_sid, Capability.STUDENT_READ, Capability.STUDENT_VIEW
        )
        students = student_service.list_students()
        return {"students": [self._student_dto(student) for student in students]}

    @staticmethod
    def _optional_date(value: Any) -> date | None:
        if value in (None, ""):
            return None
        try:
            return date.fromisoformat(str(value))
        except ValueError as exc:
            raise ProtectedDomainError("Date fields must use ISO YYYY-MM-DD format.") from exc

    def create_student(
        self,
        token: str,
        caller_sid: str,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        _, _, student_service = self._ensure_services()
        self._authorized_user(token, caller_sid, Capability.STUDENT_CREATE)
        if not isinstance(payload, Mapping):
            raise ProtectedDomainError("Student payload must be an object.")
        student = student_service.create_student(
            full_name=str(payload.get("full_name", "")),
            preferred_name=payload.get("preferred_name"),
            date_of_birth=self._optional_date(payload.get("date_of_birth")),
            gender=payload.get("gender"),
            status=payload.get("status"),
            current_level=payload.get("current_level"),
            enrollment_date=self._optional_date(payload.get("enrollment_date")),
            notes=payload.get("notes"),
        )
        return {"student": self._student_dto(student)}
