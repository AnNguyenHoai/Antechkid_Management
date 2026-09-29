from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.core.capabilities import Capability
from centermanager.core.current_user import CurrentUserContext
from centermanager.platform.backup.backup_service import BackupService
from centermanager.services.authorization_service import AuthorizationService
from centermanager.services.backup_operations_service import (
    BackupOperationsService,
    BackupRestoreAuthorizationError,
)


class FakeCollaborationManager:
    def __init__(self, writing=True):
        self.writing = writing

    def is_initialized(self):
        return True

    def is_writing(self):
        return self.writing


class FakeBackupService:
    def __init__(self):
        self.calls = []

    def create_backup(self, label="manual"):
        self.calls.append(("create", label))
        raise AssertionError("Phase A recovery gate must reject before backup mutation")

    def restore_backup(self, backup_path, *, authorization=None):
        self.calls.append(("restore", Path(backup_path), authorization))
        raise AssertionError("Phase A recovery gate must reject before raw restore")


def principal(role_name, *, is_admin=False, permissions=()):
    role = SimpleNamespace(name=role_name)
    permission_set = set(permissions)
    return SimpleNamespace(
        id=7,
        username="restore-admin" if is_admin else "staff",
        role=role,
        is_admin=is_admin,
        is_active=True,
        permissions=permission_set,
        has_permission=lambda value: value in permission_set,
    )


def build_service(*, writing=True):
    backup = FakeBackupService()
    service = BackupOperationsService(
        backup_service=backup,
        collaboration_manager=FakeCollaborationManager(writing=writing),
    )
    return service, backup


def test_backup_restore_capability_is_admin_only_even_with_direct_permission():
    user = principal(
        "manager",
        permissions={Capability.BACKUP_RESTORE.value},
    )
    assert not AuthorizationService.allows(user, Capability.BACKUP_RESTORE)


def test_raw_backup_restore_rejects_missing_authorization_before_platform_access():
    service = BackupService.__new__(BackupService)
    result = service.restore_backup(Path("/does/not/matter"))
    assert result.success is False
    assert "authorization context" in result.error.lower()


@pytest.mark.parametrize(
    "user,writing,error_match",
    [
        (principal("manager", is_admin=False), True, "Administrator"),
        (principal("admin", is_admin=True), True, "Finish or cancel the current editing session"),
        (principal("admin", is_admin=True), False, "Recovery authority is not available yet"),
    ],
)
def test_restore_rejections_happen_before_safety_backup(user, writing, error_match):
    service, backup = build_service(writing=writing)
    target = Path("/managed/snapshot")

    with CurrentUserContext(user):
        with pytest.raises(BackupRestoreAuthorizationError, match=error_match):
            service.restore_backup(
                target,
                reason="rollback",
                confirmation=service.confirmation_phrase(target),
            )

    assert backup.calls == []


def test_phase_a_blocks_restore_inside_normal_write_session_before_mutation():
    service, backup = build_service(writing=True)
    actor = principal("admin", is_admin=True)
    target = Path("/managed/snapshot")

    with CurrentUserContext(actor):
        with pytest.raises(
            BackupRestoreAuthorizationError,
            match="Finish or cancel the current editing session",
        ):
            service.restore_backup(
                target,
                reason="Recover verified production snapshot",
                confirmation=service.confirmation_phrase(target),
            )

    assert backup.calls == []


def test_phase_a_blocks_restore_from_read_until_recovery_authority_exists():
    service, backup = build_service(writing=False)
    actor = principal("admin", is_admin=True)
    target = Path("/managed/snapshot")

    with CurrentUserContext(actor):
        with pytest.raises(
            BackupRestoreAuthorizationError,
            match="Recovery authority is not available yet",
        ):
            service.restore_backup(
                target,
                reason="Recover verified production snapshot",
                confirmation=service.confirmation_phrase(target),
            )

    assert backup.calls == []
