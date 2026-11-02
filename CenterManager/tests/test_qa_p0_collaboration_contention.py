"""QA-P0 concurrency and cross-boundary WRITE authorization tests.

All collaboration refs, clients and SQLCipher workspaces are synthetic;
existing E0/E1B-2B fixtures isolate them from production.
"""
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest
from sqlalchemy import update

from tests.test_e0_write_recovery_audit import machines  # noqa: F401
from tests.test_e1b2a_post_publish_consistency import reporting  # noqa: F401
from tests.test_e1b2b_local_mutation_authority import (
    raw, assert_original, replace_remote_owner,
)
from centermanager.database.engine import release_runtime_dbapi_connection
from centermanager.database.mutation_authority import MutationAuthorityError
from centermanager.models.student import Student
from centermanager.services.student_service import StudentService
from centermanager.services.write_transaction import WriteTransactionState


@pytest.mark.parametrize("client_count", [2, 3, 4])
def test_simultaneous_requests_never_grant_multiple_remote_owners(machines, client_count):
    """Real isolated Git refs, concurrent CAS; not an in-memory fake lease."""
    clients = [machines(f"qa-client-{i}")[0] for i in range(client_count)]
    barrier = threading.Barrier(client_count)

    def acquire(manager):
        barrier.wait(timeout=15)
        return manager.request_write()

    with ThreadPoolExecutor(max_workers=client_count) as executor:
        futures = [executor.submit(acquire, manager) for manager in clients]
        outcomes = [future.result(timeout=90) for future in futures]

    granted = [client for client, outcome in zip(clients, outcomes) if outcome.is_granted]
    assert len(granted) == 1, "Multiple simultaneous owners or no valid winner"
    assert sum(client.is_writing() for client in clients) == 1
    status = clients[0].get_lock_status()
    assert status["session_id"] == granted[0].get_session_id()
    assert status["state"] == "ACTIVE"


def test_old_session_cannot_release_new_same_username_owner(machines):
    """Same principal is not an authorization token for session-targeted release."""
    old, old_provider = machines("qa-old", username="same-account")
    new, new_provider = machines("qa-new", username="same-account")
    assert old.request_write().is_granted
    old_session = old.get_session_id()
    old_oid = old_provider._remote_lock_oid()
    assert old.release_write()
    assert new.request_write().is_granted
    current_oid = new_provider._remote_lock_oid()
    current_session = new.get_session_id()
    assert current_session != old_session
    assert current_oid != old_oid

    assert not old_provider.release_lock(
        "same-account", session_id=old_session, expected_oid=old_oid
    )
    assert not old_provider.release_lock("same-account")
    assert new_provider._remote_lock_oid() == current_oid
    assert new_provider.remote_lock_status()["session_id"] == current_session
    assert new.is_writing()


@pytest.mark.parametrize("boundary", ["service", "orm", "bulk", "dbapi"])
def test_authority_loss_denies_separate_mutation_paths(reporting, boundary):
    """Fresh SQLCipher workspace per case; no post-loss business update accepted."""
    w = reporting
    assert w.tx.start_editing(), w.tx.last_start_error
    replace_remote_owner(w)
    with pytest.raises(MutationAuthorityError):
        if boundary == "service":
            StudentService(w.factory).update_student(1, full_name="STALE service")
        elif boundary == "dbapi":
            conn = raw(w)
            try:
                conn.execute("UPDATE students SET full_name=? WHERE id=1", ("STALE dbapi",))
                conn.commit()
            finally:
                release_runtime_dbapi_connection(conn)
        else:
            with w.factory() as session:
                if boundary == "orm":
                    session.get(Student, 1).full_name = "STALE ORM"
                else:
                    session.execute(
                        update(Student).where(Student.id == 1).values(full_name="STALE bulk")
                    )
                session.commit()
    assert_original(w)
    assert w.tx.state == WriteTransactionState.RECOVERY_REQUIRED
    document = w.journal.inspect()
    assert document["mutation_authority_lost"]
    assert document["status"] == "OPEN"
