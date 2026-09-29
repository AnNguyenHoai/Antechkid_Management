from datetime import datetime, timedelta
from threading import RLock
from types import SimpleNamespace

from centermanager.platform.backup.recovery_authority import RecoveryAuthority


class _LocalLock:
    def __init__(self):
        self.data = {"locked": False}

    def _write_lock(self, data):
        self.data = dict(data)

    def _force_release(self):
        self.data = {"locked": False}

    def get_lock_info(self):
        return dict(self.data)


class _ProjectedSyncProvider:
    """Model the production provider's public remote-lock projection.

    The raw Git lock preserves arbitrary fields such as authority_mode, but
    remote_lock_status() historically projects only the canonical lock fields.
    """

    def __init__(self):
        self.raw = None
        self.released = False

    def acquire_lock(self, lock_data):
        self.raw = dict(lock_data)
        return True

    def renew_lock(self, owner, session_id):
        if not self.raw:
            return False
        if self.raw.get("owner") != owner or self.raw.get("session_id") != session_id:
            return False
        self.raw["lease_expires_at"] = (
            datetime.now() + timedelta(seconds=60)
        ).isoformat()
        return True

    def release_lock(self, owner):
        if self.raw and self.raw.get("owner") == owner:
            self.raw = None
            self.released = True
            return True
        return False

    def projected_status(self):
        if not self.raw:
            return {"locked": False, "owner": None, "session_id": None}
        # Intentionally omit authority_mode/reason to reproduce packaged UAT.
        return {
            "locked": self.raw.get("locked", False),
            "owner": self.raw.get("owner"),
            "session_id": self.raw.get("session_id"),
            "lease_expires_at": self.raw.get("lease_expires_at"),
        }


class _Manager:
    def __init__(self):
        self._sync_provider = _ProjectedSyncProvider()
        self._lock = _LocalLock()
        self._state_mutex = RLock()
        self._session = SimpleNamespace(username="admin", session_id="sec06-session")
        self._writing = False
        self._projected_mode = None

    def is_initialized(self):
        return True

    def is_writing(self):
        return self._writing

    def get_session(self):
        return self._session

    def _build_lock_data(self):
        return {
            "locked": True,
            "owner": self._session.username,
            "username": self._session.username,
            "session_id": self._session.session_id,
            "lease_expires_at": (datetime.now() + timedelta(seconds=60)).isoformat(),
        }

    def _get_remote_lock_status(self):
        status = self._sync_provider.projected_status()
        if self._projected_mode is not None:
            status["authority_mode"] = self._projected_mode
        return status

    @staticmethod
    def _is_lease_valid(value):
        return bool(value and datetime.now() < datetime.fromisoformat(value))


def test_remote_recovery_authority_survives_provider_projection_and_local_write_flag():
    manager = _Manager()
    authority = RecoveryAuthority(manager)

    assert authority.acquire() is True
    assert manager._sync_provider.raw["authority_mode"] == "RECOVERY"
    assert manager._sync_provider.raw["reason"] == "backup_restore"

    # Reproduce the second SEC06 UAT failure: the provider projection omits the
    # custom mode, while background local projection may mark the same lease as
    # writing. The distributed session/owner/lease still prove our authority.
    manager._writing = True
    assert authority.validate() is True
    assert authority.renew() is True

    authority.release()
    assert manager._sync_provider.released is True


def test_remote_recovery_authority_rejects_explicit_non_recovery_mode():
    manager = _Manager()
    authority = RecoveryAuthority(manager)

    assert authority.acquire() is True
    manager._projected_mode = "WRITE"

    assert authority.validate() is False
    authority.release()


def test_remote_recovery_authority_rejects_replaced_session():
    manager = _Manager()
    authority = RecoveryAuthority(manager)

    assert authority.acquire() is True
    manager._session = SimpleNamespace(username="admin", session_id="replacement-session")

    assert authority.validate() is False
