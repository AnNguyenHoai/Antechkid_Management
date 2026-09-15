# -*- coding: utf-8 -*-
"""3.3.5-B.2 deterministic three-client rotation contention regression."""

from centermanager.events.event_bus import EventBus
from centermanager.platform.collaboration import CollaborationManager


def _make_clients(runtime_root):
    event_bus = EventBus()
    clients = [
        CollaborationManager(runtime_root=runtime_root, event_bus=event_bus, sync_provider=None)
        for _ in range(3)
    ]
    identities = [
        ("user_a", "User A"),
        ("user_b", "User B"),
        ("user_c", "User C"),
    ]
    for client, (user_id, username) in zip(clients, identities):
        client.initialize(user_id, username, "admin")
    return clients


def _assert_single_writer(clients, expected_index):
    states = [client.is_writing() for client in clients]
    assert sum(states) == 1, f"expected exactly one writer, got {states}"
    assert states[expected_index] is True


def test_three_client_rotation_two_full_cycles(tmp_path):
    """
    Deterministic ownership rotation must preserve FIFO across two full cycles:

        A -> B -> C -> A -> B -> C

    Every handoff is exercised through the real queue/head guard. A later waiter
    may not bypass the current queue head, and every previous writer must have
    returned to READ before the next writer is granted.
    """
    clients = []
    try:
        clients = _make_clients(tmp_path / "runtime")
        cm_a, cm_b, cm_c = clients

        # Cycle 1 starts with A owning WRITE. B and C join in FIFO order.
        first = cm_a.request_write()
        assert first.is_granted
        _assert_single_writer(clients, 0)

        b_wait_1 = cm_b.request_write()
        c_wait_1 = cm_c.request_write()
        assert b_wait_1.is_waiting
        assert c_wait_1.is_waiting
        assert [r["request_id"] for r in cm_a.get_queue()["requests"]] == [
            b_wait_1.request_id,
            c_wait_1.request_id,
        ]

        # A -> B. C cannot bypass B.
        assert cm_a.release_write()
        assert not any(client.is_writing() for client in clients)
        assert cm_c.grant_existing_waiting_request(c_wait_1.request_id) is False
        assert cm_b.grant_existing_waiting_request(b_wait_1.request_id) is True
        _assert_single_writer(clients, 1)

        # B -> C.
        assert cm_b.release_write()
        assert cm_c.grant_existing_waiting_request(c_wait_1.request_id) is True
        _assert_single_writer(clients, 2)

        # Cycle 2: while C writes, A then B request again.
        a_wait_2 = cm_a.request_write()
        b_wait_2 = cm_b.request_write()
        assert a_wait_2.is_waiting
        assert b_wait_2.is_waiting
        assert [r["request_id"] for r in cm_c.get_queue()["requests"]] == [
            a_wait_2.request_id,
            b_wait_2.request_id,
        ]

        # C -> A. B still cannot bypass A.
        assert cm_c.release_write()
        assert not any(client.is_writing() for client in clients)
        assert cm_b.grant_existing_waiting_request(b_wait_2.request_id) is False
        assert cm_a.grant_existing_waiting_request(a_wait_2.request_id) is True
        _assert_single_writer(clients, 0)

        # A -> B.
        assert cm_a.release_write()
        assert cm_b.grant_existing_waiting_request(b_wait_2.request_id) is True
        _assert_single_writer(clients, 1)

        # B releases: second full rotation is complete and queue is empty.
        assert cm_b.release_write()
        assert not any(client.is_writing() for client in clients)
        assert cm_a.get_queue_length() == 0
        assert cm_a.get_queue()["requests"] == []
        assert cm_b.get_queue()["next"] is None
    finally:
        for client in reversed(clients):
            try:
                client.shutdown()
            except Exception:
                pass
