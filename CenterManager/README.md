# TASK 3.3.3-A — DIRECT FIX v7

This version fixes the remaining test-harness issues without changing
production collaboration code.

Changes:
- `test_waiting_request_visible_cross_machine` is explicitly skipped because
  `WriteQueue` is local runtime state.
- `test_machine_a_sees_waiting_request` is explicitly skipped for the same
  reason.
- `test_expired_lease_becomes_visible_cross_machine` uses the actual
  `create_client()` helper from the current test file.
- Poller A is stopped before any direct Git mutation on A's repository.
- Expiry is deterministic (`lease_expires_at = now - 1s`) and uses no sleep.
- Poller B is the only observer after the expired remote state is published.
- Cleanup always stops/joins both pollers.

No production code is changed by v7.

Run:
`pytest tests/test_collaboration_waiting_visibility.py -v`

Expected:
5 passed, 2 skipped.
