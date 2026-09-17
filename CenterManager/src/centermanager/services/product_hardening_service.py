"""Cross-cutting product-hardening guards.

This module deliberately stays small: it centralizes invariants that must hold
across existing services without introducing a second domain architecture.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from centermanager.services.authorization_service import AuthorizationService
from centermanager.core.capabilities import Capability


class ProductHardeningService:
    """Common guard helpers used by hardened application boundaries."""

    @staticmethod
    def require_capability(user: Any, capability: Capability | str) -> None:
        AuthorizationService.require(user, capability)

    @staticmethod
    def require_managed_path(path: Path, root: Path) -> Path:
        candidate = Path(path).resolve()
        managed_root = Path(root).resolve()
        try:
            candidate.relative_to(managed_root)
        except ValueError as exc:
            raise ValueError("Path is outside the managed runtime boundary.") from exc
        return candidate
