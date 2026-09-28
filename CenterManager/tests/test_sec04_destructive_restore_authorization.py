from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.core.capabilities import Capability
from centermanager.core.current_user import CurrentUserContext
from centermanager.platform.backup.backup_service import BackupResult, BackupService
from centermanager.services.authorization_service import AuthorizationService
from centermanager.services.backup_operations_service import (
    BackupOperationsService,
    BackupRestoreAuthorizationError,
    BackupRestoreValidationError,
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
        self.safety_path = Path("/managed/pre_restore")

    def create_backup(self, label="manual"):
        self.calls.append(("create", label))
        return BackupResult(True, self.safety_path)

    def restore_backup(self, backup_path, *, authorization=None):
        self.calls.append(("restore", Path(backup_path), authorization))
        return BackupResult(True, Path(backup_path))


class FakeAuditService:
    def __init__(self):
        self.calls = []

    def record(self, *args, **kwargs):
        self.calls.append((args, kwargs))


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
    audit = FakeAuditService()
    service = BackupOperationsService(
        backup_service=backup,
        audit_service=audit,
        collaboration_manager=FakeCollaborationManager(writing=writing),
    )
    return service, backup, audit


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
    "user,writing,reason,confirmation,error_type",
    [
        (principal("manager", is_admin=False), True, "rollback", "RESTORE snapshot", BackupRestoreAuthorizationError),
        (principal("admin", is_admin=True), False, "rollback", "RESTORE snapshot", BackupRestoreAuthorizationError),
        (principal("admin", is_admin=True), True, "", "RESTORE snapshot", BackupRestoreValidationError),
        (principal("admin", is_admin=True), True, "rollback", "WRONG", BackupRestoreValidationError),
    ],
)
def test_restore_rejections_happen_before_safety_backup(
    user, writing, reason, confirmation, error_type
):
    service, backup, _ = build_service(writing=writing)
    with CurrentUserContext(user):
        with pytest.raises(error_type):
            service.restore_backup(
                Path("/managed/snapshot"),
                reason=reason,
                confirmation=confirmation,
            )
    assert backup.calls == []


def test_authorized_restore_rechecks_write_and_audits_real_actor():
    service, backup, audit = build_service(writing=True)
    actor = principal("admin", is_admin=True)
    target = Path("/managed/snapshot")

    with CurrentUserContext(actor):
        result = service.restore_backup(
            target,
            reason="Recover verified production snapshot",
            confirmation=service.confirmation_phrase(target),
        )

    assert result.success is True
    assert [call[0] for call in backup.calls] == ["create", "restore"]
    authorization = backup.calls[1][2]
    assert authorization.reason == "Recover verified production snapshot"
    assert authorization.actor_id == actor.id
    assert len(audit.calls) == 1
    assert audit.calls[0][1]["actor"] is actor
    assert audit.calls[0][1]["details"]["reason"] == "Recover verified production snapshot"


def test_write_loss_after_safety_backup_blocks_raw_restore():
    manager = FakeCollaborationManager(writing=True)

    class LoseWriteBackup(FakeBackupService):
        def create_backup(self, label="manual"):
            result = super().create_backup(label)
            manager.writing = False
            return result

    backup = LoseWriteBackup()
    service = BackupOperationsService(
        backup_service=backup,
        audit_service=FakeAuditService(),
        collaboration_manager=manager,
    )
    actor = principal("admin", is_admin=True)
    target = Path("/managed/snapshot")

    with CurrentUserContext(actor):
        with pytest.raises(BackupRestoreAuthorizationError):
            service.restore_backup(
                target,
                reason="rollback",
                confirmation=service.confirmation_phrase(target),
            )

    assert [call[0] for call in backup.calls] == ["create"]
