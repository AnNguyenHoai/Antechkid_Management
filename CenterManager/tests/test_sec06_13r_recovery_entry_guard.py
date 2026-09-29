import pytest

from centermanager.platform.backup.recovery_authority import RecoveryAuthority
from centermanager.services.backup_operations_service import (
    BackupOperationsService,
    BackupRestoreAuthorizationError,
)


class _CollaborationStub:
    def __init__(self, *, initialized=True, writing=False, fail=False):
        self._initialized = initialized
        self._writing = writing
        self._fail = fail

    def is_initialized(self):
        if self._fail:
            raise RuntimeError("collaboration unavailable")
        return self._initialized

    def is_writing(self):
        if self._fail:
            raise RuntimeError("collaboration unavailable")
        return self._writing


def _service(manager):
    return BackupOperationsService(
        backup_service=object(),
        collaboration_manager=manager,
    )


def test_recovery_entry_rejects_normal_editing_session():
    service = _service(_CollaborationStub(writing=True))

    with pytest.raises(
        BackupRestoreAuthorizationError,
        match="Finish or cancel the current editing session",
    ):
        service._recovery_authority()


def test_recovery_entry_in_read_returns_dedicated_authority_without_entering_write():
    manager = _CollaborationStub(writing=False)
    service = _service(manager)

    authority = service._recovery_authority()

    assert isinstance(authority, RecoveryAuthority)
    assert authority.manager is manager
    assert manager.is_writing() is False


def test_recovery_entry_fails_closed_when_collaboration_state_cannot_be_verified():
    service = _service(_CollaborationStub(fail=True))

    with pytest.raises(
        BackupRestoreAuthorizationError,
        match="Unable to verify recovery entry state",
    ):
        service._recovery_authority()


def test_recovery_entry_fails_closed_when_collaboration_is_not_initialized():
    service = _service(_CollaborationStub(initialized=False))

    with pytest.raises(
        BackupRestoreAuthorizationError,
        match="initialized collaboration session",
    ):
        service._recovery_authority()
