# TASK 3.3.3-A — DIRECT FIX v8

Final test-harness correction for expired lease visibility.

Root cause:
`CollaborationSnapshot.is_stale` means the poll operation failed and is not
the semantic representation of an expired remote lease. The poller correctly
keeps the raw remote lock payload in a successful snapshot.

Therefore the test now verifies:
- B poll completed successfully.
- B observed `lease_expires_at`.
- `lease_expires_at` is in the past.
- snapshot is not marked stale merely because the remote lease is expired.

No production code changed.

Expected targeted result:
5 passed, 2 skipped.
