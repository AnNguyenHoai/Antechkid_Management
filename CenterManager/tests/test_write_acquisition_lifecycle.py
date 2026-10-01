import inspect
from types import SimpleNamespace

from centermanager import app
from centermanager.platform.bootstrap.bootstrap_manager import BootstrapManager
from centermanager.platform.collaboration import WriteRequestResult
from centermanager.services.write_transaction import (
    WriteTransactionManager,
    WriteTransactionState,
)


class _Result:
    def __init__(self, result, message="", position=0, request_id="req-1"):
        self.result = result
        self.message = message
        self.position = position
        self.request_id = request_id

    @property
    def is_granted(self):
        return self.result == WriteRequestResult.GRANTED

    @property
    def is_waiting(self):
        return self.result == WriteRequestResult.WAITING


class _Provider:
    def __init__(self, remote=None):
        self.remote = remote or {"locked": False}

    def remote_lock_status(self):
        return dict(self.remote)

    def get_remote_main_commit(self):
        return "a" * 40


class _Collab:
    def __init__(self, result, provider=None):
        self.result = result
        self._sync_provider = provider
        self.released = False
        self.cancelled = False
        self._writing = result.result == WriteRequestResult.GRANTED
        self.session = SimpleNamespace(session_id="session-1", username="tester")

    def clear_finishing_data(self):
        return None

    def request_write(self):
        return self.result

    def get_session(self):
        return self.session

    def get_lock_generation(self):
        return 1

    def is_writing(self):
        return self._writing

    def release_write(self):
        self.released = True
        self._writing = False
        return True

    def cancel_waiting_request(self):
        self.cancelled = True
        return True

    @staticmethod
    def _is_lease_valid(value):
        return bool(value)


class _Sync:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def execute_write_handoff_sync(self):
        self.calls += 1
        return self.result


def test_app_reuses_bootstrap_provider_and_does_not_run_second_startup_sync():
    source = inspect.getsource(app.main)
    assert "bootstrap.get_sync_provider()" in source
    assert "StartupSynchronization(" not in source
    assert "QLockFile" in source


def test_bootstrap_retains_authoritative_sync_provider_slot():
    bootstrap = BootstrapManager()
    provider = object()
    bootstrap._sync_provider = provider
    assert bootstrap.get_sync_provider() is provider


def test_first_writer_runs_consistency_barrier_before_editing(monkeypatch):
    provider = _Provider()
    collab = _Collab(_Result(WriteRequestResult.GRANTED, "Lock acquired"), provider)
    sync = _Sync(True)
    tx = WriteTransactionManager(collab)
    tx.set_sync_service(sync)
    monkeypatch.setattr(tx, "_create_snapshot", lambda: None)

    assert tx.start_editing() is True
    assert sync.calls == 1
    assert tx.state == WriteTransactionState.EDITING
    assert collab.released is False


def test_failed_first_writer_consistency_releases_lock_and_returns_idle(monkeypatch):
    provider = _Provider()
    collab = _Collab(_Result(WriteRequestResult.GRANTED, "Lock acquired"), provider)
    sync = _Sync(False)
    tx = WriteTransactionManager(collab)
    tx.set_sync_service(sync)
    monkeypatch.setattr(tx, "_create_snapshot", lambda: None)

    assert tx.start_editing() is False
    assert sync.calls == 1
    assert collab.released is True
    assert tx.state == WriteTransactionState.IDLE
    assert "consistency verification failed" in tx.last_start_error.lower()


def test_false_waiting_is_rejected_when_remote_lock_is_free():
    provider = _Provider({"locked": False})
    collab = _Collab(
        _Result(WriteRequestResult.WAITING, "Waiting (position 1)", position=1),
        provider,
    )
    tx = WriteTransactionManager(collab)

    assert tx.start_editing() is False
    assert collab.cancelled is True
    assert tx.state == WriteTransactionState.IDLE
    assert "no active writer owns it" in tx.last_start_error.lower()
