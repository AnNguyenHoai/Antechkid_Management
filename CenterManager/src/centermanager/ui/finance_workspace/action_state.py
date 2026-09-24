# -*- coding: utf-8 -*-
"""Shared Finance UI capability/state projection helpers.

UI projection is intentionally non-authoritative. Services remain responsible
for enforcing authorization and domain rules at mutation/read boundaries.
"""
from __future__ import annotations

from centermanager.core.current_user import get_current_user
from centermanager.services.authorization_service import AuthorizationService


def has_capability(capability) -> bool:
    user = get_current_user()
    return bool(user and AuthorizationService.allows(user, capability))


def can_mutate(
    *,
    write_enabled: bool,
    capability,
    domain_allowed: bool = True,
) -> bool:
    return bool(
        write_enabled
        and domain_allowed
        and has_capability(capability)
    )
