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


## Follow-up: remote read-only evidence and reproduced source-level stale WAITING race

After the founder confirmed WAITING position 1 persisted beyond two minutes, a **read-only** GitHub API observation of the official `Antechkid_CenterManager_DatabaseOfficial` repository returned:
- `refs/heads/lock-main` absent (HTTP 404); no recorded WRITE lock on this ref **at observation time**.
- `refs/heads/queue-main` present; its `queue.json` blob was `{"requests": []}`.
- Historic queue commits show a request appeared around 2026-11-03 17:17:58 Asia/Ho_Chi_Minh then the queue returned to empty by about 17:18:20. This does NOT reveal why the request disappeared, whether it belonged to the screenshot session, or whether another remote was used by that EXE.

**Confirmed code race:** `CollaborationPoller._poll` emitted `snapshot_changed` only when lock/queue/version changed. A queue request can be added and removed entirely between polling windows. If the most recent snapshot was already empty, the new empty snapshot compares equal, no UI callback is emitted, and `MainWindow._reconcile_waiting_transaction` never gets a successful post-request observation to clear local `WriteTransactionState.WAITING`. A stale position-1 message can persist despite authoritative queue-main being empty.

### Implemented fix in PR #551

1. The poller now emits a **fresh successful authoritative snapshot for each poll while a local pending WRITE request exists**, even if the remote lock/queue payload is unchanged. This permits the MainWindow's existing exact-session and request-id reconciliation to confirm deletion and exit WAITING; malformed/failed remote observations remain fail-closed.
2. The manager exposes a non-sensitive last handoff failure code (e.g. `GIT_LOCK_ACQUISITION_FAILED`, `QUEUE_HEAD_MISMATCH`, `MAIN_HANDOFF_FAILED`, `OWNERSHIP_VERIFICATION_FAILED`, `CLOCK_SKEW_GRACE`) instead of silent False. The poller records failed head handoffs by code while preserving queue integrity and Git CAS.
3. MainWindow waiting top-bar no longer renders `Waiting (pos 1) - None`; it reports pending Git validation or the last handoff reason.
4. Application Shell no longer claims another editor is active merely because a local WAITING request exists.
5. Regressions: remote ABSENT + current queue-head + failed Git acquisition stays READ and reports code, then valid retry gets WRITE; GRACE never grants; successful empty queue observation transitions local WAITING to idle; unchanged snapshots continue to notify while pending local intent; a no-editor WAITING top bar provides accurate guidance.

### Release gate / safety

- This corrects a **proven stale-UI reconciliation race**; it does **not** conclusively identify the *original* reason an enqueue/lock acquisition failed on the Windows EXE. A separate Git remote, release build mismatch, missing PAT permission on `lock-main`, or blocked MAIN handoff can still cause WRITE to fail.
- Never force-release Git lock, shorten grace, convert WAITING to WRITE without exact remote lock ownership, or bypass the E1B unpublished-local-change journal.
- Confirm exact-head Windows CI and repeat on a disposable EXE/runtime clone; record Git provider lock failure codes and timestamps, verify the repository URL/branch in EXE configuration (without exposing credentials). Do not merge until these gates are met.
