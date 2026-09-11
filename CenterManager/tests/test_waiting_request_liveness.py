from datetime import datetime, timedelta
import json

from centermanager.platform.collaboration.write_queue import WriteQueue, WriteRequest
from centermanager.platform.collaboration.arbitration import Priority


def test_refresh_keeps_waiting_request_alive(tmp_path):
    queue = WriteQueue(tmp_path)
    req = WriteRequest(
        request_id="req-1",
        session_id="session-1",
        user_id="user-1",
        username="User 1",
        role="teacher",
        priority=Priority.from_role("teacher"),
        timestamp=datetime.now() - timedelta(seconds=121),
        reason="edit",
        status="pending",
    )
    queue.enqueue(req)

    # A stale request would normally be removed by _list_requests().
    assert queue.get_by_session("session-1") is None

    # Recreate the request, then renew it before the next expiry sweep.
    queue.enqueue(req)
    assert queue.refresh("req-1") is True
    refreshed = queue.get_by_session("session-1")
    assert refreshed is not None
    assert (datetime.now() - refreshed.timestamp).total_seconds() < 5
