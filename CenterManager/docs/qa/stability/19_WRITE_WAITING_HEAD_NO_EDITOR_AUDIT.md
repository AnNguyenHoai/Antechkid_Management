# WRITE-QUEUE-HANDOFF-01 — Position 1 with no visible active editor (source audit)

**Date** 2026-11-03. **Base** `main_repos` at `bf44dee53ae1058e096f8b280ef0ebae570925f9`. Screenshot supplied by founder. **No production changes / no remote mutations**.

## Symptom observed
Windows EXE title strip: `Mode: READ`, `No active editor`, `Waiting (pos 1) - None`; banner says `Another edit session is active. Your request will continue when editing becomes available.` and `Waiting (position 1)`. The Start Editing action says Waiting with Cancel request visible.

Interpretation: local `WriteTransaction` is WAITING; a queue position was confirmed or retained. Neither `No active editor` nor position 1 proves lock *acquisition* or publication permission. Do not force-release remote lock based on screenshot.

## Trace / relevant code
- `WriteTransaction.start_editing()` asks `CollaborationManager.request_write()`; on WAITING stores the exact request id, position, and a timestamp. UI top bar is updated from local transaction.
- `CollaborationManager._request_remote_write()` enqueues first, then attempts `_grant_remote_request(..., run_handoff=False)` if remote lock is not ACTIVE/GRACE. Failed acquisition can still report WAITING as a legitimate queue-head state.
- `CollaborationPoller._poll()` fetches remote lock and queue, then calls `_try_handoff_waiting_request()`. It may only attempt a grant when the local session matches the head of the freshly fetched queue and the lock is eligible.
- `CollaborationManager._grant_remote_request()` checks exact queue identity, clock-skew GRACE, CAS lock acquisition, post-acquisition queue head, synchronous main database handoff, CAS queue consumption and exact remote session ownership. Any failure returns False and retains a safe non-WRITE state.
- `MainWindow._update_waiting_status()` displays `No active editor` if the observed lock is neither ACTIVE nor GRACE/UNKNOWN but `_transaction` remains WAITING. The top status text in `_update_write_buttons()` uses position + owner even if owner is absent, hence `Waiting (pos 1) - None`.
- `lock_observation.observe_lock()` distinguishes ABSENT, ACTIVE, GRACE (default tolerance 600 seconds), RECLAIMABLE and UNKNOWN. Clock-skew grace MUST NOT be bypassed.
- `CollaborationPoller.get_status()` exposes running, mode, poll_in_progress, consecutive_failures, current_backoff, last_poll_at, last_success_at, snapshot_stale and observation_paused. Use this alongside remote lock/queue observations for a reproducible diagnosis.

## Hypotheses to distinguish (not proven from image)
1. **Transient lock/queue handoff:** queue-head pending until next successful poll. Determine whether WAITING clears automatically after one waiting interval.
2. **Stale/ungranted lock candidate:** `_ungranted_lock` and `_rollback_ungranted_lock()` may prevent new candidate until exact session-targeted release is acknowledged. Never clear this flag without remote verification.
3. **Git failure / CAS rejection:** `GitSynchronizationProvider.acquire_lock()` can return False when the lock ref is still valid, commit creation fails, push CAS fails, or post-push ownership verification fails. See logs `Atomic lock acquisition started`, `Lock already held`, `Failed to create lock commit`, `Failed to push lock branch`.
4. **Poller stalled/paused:** if no successful poll/handoff after waiting, inspect `get_status()` running, observation_paused, failures, backoff, and actual last success; do not assume UI 'Sync idle' means collaboration Git polling healthy.
5. **GRACE or ambiguous authority:** a remote lease can look expired in one status projection but still have an enforcing clock-skew safety interval. A network UNKNOWN must never be treated as ABSENT.
6. **UI state ambiguity:** `Waiting (pos 1) - None` is a display issue when there is no known editor; it is not evidence that WRITE is already grantable.

## P0 diagnostics needed from a *read-only* observation
Record, at the same timestamp, **the sanitized** state, request position/id redacted, lock state (ABSENT / RECLAIMABLE / GRACE / ACTIVE / UNKNOWN), lease expiry (no token), queue head matching current session (yes/no), poller status (running/stale/backoff/paused), last Git lock error category and whether a candidate rollback/handoff is in progress. Avoid usernames, local file contents, SQL, Git PAT or auth headers in exported logs.

Capture source log lines around Start Editing and next two polls:
`Start Editing collaboration result=`, `Write transaction waiting`, `Atomic lock acquisition started`, `Lock already held`, `Failed to push lock branch`, `Automatic collaboration handoff`, `Poll failed`, `WRITE request acknowledgement is unknown`.
Only log error code/stage + correlation ID in future product diagnostics; do not expose raw Git stderr, token or student data.

## Regression scenarios required before fixing authority code
W01 ABSENT lock with confirmed current queue head automatically reaches WRITE after successful preflight; W02 RECLAIMABLE after tolerance reaches WRITE; W03 GRACE remains WAITING and remains read-only; W04 queue head belongs to another session remains WAITING; W05 Git CAS rejected leaves WAITING with meaningful diagnostic and never creates an unauthorized local writer; W06 failed handoff MAIN consistency leaves queued intent safe and doesn't consume head; W07 stalled poller shows stale/unknown rather than 'No active editor'; W08 cancel pending only after remote acknowledgement, with old request unable to grant later; W09 two Windows clients simultaneously requesting WRITE: only one exact session wins; W10 owner crash and restart preserving E1B recovery journal, no local DB overwrite.

## Remediation recommendation
Do not alter the 600s GRACE, remove CAS, force-drop collaboration refs, or self-grant WRITE. First add bounded read-only handoff diagnostics to the waiting UI and test the exact branch causing the stall. If screenshot's status persists beyond the expected poll interval with remote ABSENT and current head confirmed, treat as a real auto-handoff bug and inspect provider acquisition and poller lifecycle. Avoid unrelated DB and Git MAIN migrations.
