import pytest

from centermanager.platform.backup.recovery_publisher import (
    AuthoritativeRecoveryPublisher,
    RecoveryPublishError,
)


class AuthorityStub:
    def __init__(self, validations):
        self._validations = iter(validations)

    def validate(self):
        return next(self._validations)


class RuntimeSyncStub:
    def __init__(self, result=True):
        self.result = result
        self.calls = []

    def publish_only(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


def test_recovery_publish_requires_live_authority_before_remote_mutation():
    sync = RuntimeSyncStub()
    publisher = AuthoritativeRecoveryPublisher(sync)

    with pytest.raises(RecoveryPublishError, match="authority is required"):
        publisher.publish(
            authority=AuthorityStub([False]),
            actor_name="admin",
            backup_name="snapshot",
        )

    assert sync.calls == []


def test_recovery_publish_uses_publish_only_and_preserves_recovery_mode():
    sync = RuntimeSyncStub(result=True)
    publisher = AuthoritativeRecoveryPublisher(sync)

    publisher.publish(
        authority=AuthorityStub([True, True]),
        actor_name="admin",
        backup_name="snapshot",
        expected_main_commit="abc123",
    )

    assert sync.calls == [{
        "message": "Recovery restore: snapshot",
        "user": "admin",
        "expected_main_commit": "abc123",
    }]


def test_recovery_publish_fails_closed_when_provider_publish_fails():
    sync = RuntimeSyncStub(result=False)
    publisher = AuthoritativeRecoveryPublisher(sync)

    with pytest.raises(RecoveryPublishError, match="publish failed"):
        publisher.publish(
            authority=AuthorityStub([True]),
            actor_name="admin",
            backup_name="snapshot",
        )


def test_recovery_publish_fails_if_authority_is_lost_during_publish():
    sync = RuntimeSyncStub(result=True)
    publisher = AuthoritativeRecoveryPublisher(sync)

    with pytest.raises(RecoveryPublishError, match="lost during"):
        publisher.publish(
            authority=AuthorityStub([True, False]),
            actor_name="admin",
            backup_name="snapshot",
        )
