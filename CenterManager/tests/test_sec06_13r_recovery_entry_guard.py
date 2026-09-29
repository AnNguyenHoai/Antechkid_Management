import pytest

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
    # A backup service is not needed because Phase A must reject before any
    # backup/restore mutation can be reached.
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
        service._require_recovery_entry_state()


def test_recovery_entry_fails_closed_in_read_until_recovery_authority_exists():
    service = _service(_CollaborationStub(writing=False))

    with pytest.raises(
        BackupRestoreAuthorizationError,
        match="Recovery authority is not available yet",
    ):
        service._require_recovery_entry_state()


def test_recovery_entry_fails_closed_when_collaboration_state_cannot_be_verified():
    service = _service(_CollaborationStub(fail=True))

    with pytest.raises(
        BackupRestoreAuthorizationError,
        match="Unable to verify recovery entry state",
    ):
        service._require_recovery_entry_state()
