from types import SimpleNamespace

from centermanager.core.capabilities import (
    ADMIN_ONLY_CAPABILITIES,
    PERSISTED_CAPABILITIES,
    Capability,
)
from centermanager.services.authorization_service import AuthorizationService


def _principal(role_name: str, permissions=()):
    return SimpleNamespace(
        role=SimpleNamespace(name=role_name),
        permissions=set(permissions),
        is_active=True,
    )


def test_backup_surface_capabilities_are_admin_only():
    expected = {
        Capability.BACKUP_VIEW.value,
        Capability.BACKUP_CREATE.value,
        Capability.BACKUP_RESTORE.value,
    }

    assert expected <= ADMIN_ONLY_CAPABILITIES
    assert expected.isdisjoint(PERSISTED_CAPABILITIES)


def test_admin_can_create_backup_without_persisted_permission_rows():
    admin = _principal("admin")

    assert AuthorizationService.allows(admin, Capability.BACKUP_VIEW)
    assert AuthorizationService.allows(admin, Capability.BACKUP_CREATE)
    assert AuthorizationService.allows(admin, Capability.BACKUP_RESTORE)


def test_non_admin_cannot_gain_backup_maintenance_capabilities_from_role_rows():
    manager = _principal(
        "manager",
        permissions={
            Capability.BACKUP_VIEW.value,
            Capability.BACKUP_CREATE.value,
            Capability.BACKUP_RESTORE.value,
        },
    )

    assert not AuthorizationService.allows(manager, Capability.BACKUP_VIEW)
    assert not AuthorizationService.allows(manager, Capability.BACKUP_CREATE)
    assert not AuthorizationService.allows(manager, Capability.BACKUP_RESTORE)
